# Bug修复记录：管理后台任务触发无响应

**Phase**：Phase 17  
**日期**：2026-08-19  
**提交范围**：`d2c63a4` ~ `430093a`  
**严重程度**：中（影响管理员操作体验，但不影响核心功能）  
**影响范围**：管理后台所有手动触发任务的场景

---

## 问题现象

用户在管理后台点击"生成AI总结"按钮后，无任何反馈，任务未执行。后端返回 200 OK，但实际任务未入队。

---

## 根本原因

1. **僵尸任务阻塞**：21天前（`id=1061`）有一个手动触发的 `summarize` 任务启动后一直卡在 `status=running` 状态（`started_at=1785390764`, `finished_at=NULL`），可能由于：
   - Celery worker 崩溃/重启，任务未正常收尾
   - 任务执行过程中异常退出，未触发 `finish_job()`
   - 数据库事务未提交或其他持久化问题

2. **并发锁无超时机制**：`jobs.any_running()` 简单检查是否存在 `status=running` 的记录，无超时自动清理逻辑，导致僵尸任务永久占用"锁"。

3. **前端无明确反馈**：当后端返回 `{started: false, running: true}` 时（表示"已有任务运行中，拒绝新任务"），前端仅提示 `message.info("任务已在运行中")`，未说明这是**阻塞状态**还是**正常排队**，且用户看不到阻塞原因（如僵尸任务ID、启动时间）。

---

## 临时修复（已执行）

手动将僵尸任务标记为失败：
```sql
UPDATE job_runs SET status='error', finished_at=1787127000, error='僵尸任务，手动清理' WHERE id=1061;
```

---

## 永久修复方案

### 1. 后端：自动清理超时僵尸任务

**文件**：`backend/app/repositories/jobs.py`

**改动**：在 `any_running()` 检查前，自动清理 `started_at` 距今超过 2 小时且仍为 `running` 的任务。

```python
async def any_running(session: AsyncSession, kind: str) -> bool:
    """检查是否有正在运行的任务，自动清理超时僵尸任务（超过 2 小时未完成视为异常）。"""
    now = int(time.time())
    timeout_seconds = 2 * 3600  # 2 小时

    # 先清理僵尸任务：started_at 距今超过 2 小时且仍然 running
    await session.execute(text(
        """
        UPDATE job_runs
        SET status = 'error', finished_at = :now, error = '任务超时，自动标记失败'
        WHERE kind = :k AND status = 'running' AND started_at < :threshold
        """
    ), {"k": kind, "now": now, "threshold": now - timeout_seconds})
    await session.commit()

    # 再检查是否还有 running 任务
    return (await session.execute(text(
        "SELECT 1 FROM job_runs WHERE kind = :k AND status = 'running' LIMIT 1"
    ), {"k": kind})).first() is not None
```

**优点**：
- 无需定时任务，每次触发新任务时自动清理
- 2 小时超时窗口足够覆盖正常任务（采集+总结通常 < 30 分钟）
- 僵尸任务被标记为 `error` 后，管理员可在历史记录中看到"任务超时，自动标记失败"

### 2. 后端：返回明确的错误提示

**文件**：`backend/app/api/routers/admin/jobs.py`

**改动**：当检测到任务正在运行时，返回 `error` 字段说明原因。

```python
@router.post("/summarize")
async def summarize(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.summarize import task_summarize
    body = await _json_body(request)
    ptype = body.get("type", "daily")
    if ptype not in PERIOD_TYPES:
        return {"started": False, "error": "未知的总结类型"}
    if await jobs.any_running(session, "summarize"):
        return {"started": False, "running": True, "error": "已有任务正在运行，请稍后再试"}  # ← 新增 error
    job_id = await run_in_threadpool(jobs.create_job, "summarize", "手动")
    task_summarize.delay(
        ptype, str(body.get("start", "")), str(body.get("end", "")),
        str(body.get("user", "")), bool(body.get("regen", False)), "手动", job_id,
    )
    return {"started": True, "running": True}
```

### 3. 前端：区分正常提示与警告

**文件**：`frontend/src/pages/Admin.tsx`

**改动**：
1. `JobPanel` 组件（数据同步任务）：用 `message.warning()` 替代 `message.info()`，并显示后端返回的 `error` 字段
2. `JobPanelInline` 组件（生成AI总结）：同样改为 `message.warning()` + 显示 `error`

```typescript
// JobPanel（行 24-30）
const trigger = () => {
  api.post(triggerPath, body ?? {}).then((r) => {
    if (r.data?.started === false && r.data?.running) {
      message.warning(r.data?.error || "任务已在运行中，请稍后再试");
    } else {
      message.success("已触发");
    }
    setPolling(true);
  }).catch((e) => message.error(errMsg(e)));
};

// JobPanelInline（行 146-155）
const trigger = () => api.post(p.triggerPath, p.body)
  .then((r) => {
    if (r.data?.started === false && r.data?.running) {
      message.warning(r.data?.error || "任务已在运行中，请稍后再试");
    } else {
      message.success("已触发");
    }
    setPolling(true);
  })
  .catch((e) => message.error(errMsg(e)));
```

**用户体验改进**：
- **信息 → 警告**：用户明确知道这是**异常情况**（有任务卡住），而非正常排队
- **显示具体原因**：后端的 `error` 字段（"已有任务正在运行，请稍后再试"）比泛泛的"任务已在运行中"更明确

---

## 验证方案

1. **构造僵尸任务**：手动插入一条 `status=running, started_at=<2小时前>` 的记录
2. **触发新任务**：点击"生成AI总结"按钮
3. **预期结果**：
   - 后端自动清理僵尸任务（标记为 `error`）
   - 新任务正常创建并执行
   - 前端提示"已触发"

4. **真实并发测试**：启动一个真实的长时间任务（如全量总结），在其运行时点击按钮
5. **预期结果**：前端显示**警告**提示"已有任务正在运行，请稍后再试"（黄色消息，而非蓝色 info）

---

## 后续优化建议（可选）

### 1. Celery 任务侧兜底
在所有长时间任务（`task_crawl`、`task_summarize`、`task_stock_sync` 等）的 `finally` 块中保证无论成功失败都调用 `finish_job()`：

```python
def task_crawl(...):
    job_id = None
    try:
        job_id = jobs.create_job("crawl", source)
        # ... 执行逻辑 ...
        jobs.finish_job(job_id)
    except Exception as e:
        if job_id:
            jobs.finish_job(job_id, error=str(e))
        raise
```

**注意**：目前的任务代码已经有 `runner.py` 的 `@job_context` 装饰器包裹，理论上已经覆盖；但检查一下是否所有长时间任务都使用了该装饰器。

### 2. 管理后台增加"任务列表"页
显示最近 50 条 `job_runs` 记录（含 `status=running` 的任务），允许管理员：
- 查看每个任务的启动时间、耗时、日志
- 手动强制终止僵尸任务（调用 `/api/jobs/{id}/cancel` 接口）

### 3. 监控告警
- Prometheus + Grafana 监控 `job_runs` 表中 `status=running` 且 `started_at < now - 1小时` 的记录数
- 超过阈值（如 ≥3）时发送告警，提示可能有 worker 异常

---

## 总结

| 层级 | 问题 | 修复 |
|-----|------|------|
| **后端** | 僵尸任务永久占用"锁"，无超时清理 | `any_running()` 自动清理超时任务（2小时） |
| **后端** | 阻塞时返回的 `error` 为空 | 返回明确的 `error: "已有任务正在运行，请稍后再试"` |
| **前端** | 用 `message.info()` 提示，与正常状态无区分 | 改用 `message.warning()` + 显示后端 `error` 字段 |

**影响**：
- 用户体验：从"点击无反应"变为"立即看到警告提示+原因"
- 运维成本：从"需手动清理僵尸任务"变为"自动清理"
- 鲁棒性：避免因单次 worker 崩溃导致后续所有手动触发失败

**部署建议**：
- 后端改动无需重启 PostgreSQL，只需 `docker compose restart api worker`
- 前端改动需重新构建 `docker compose up -d --build frontend`
- 可先在测试环境验证僵尸任务清理逻辑，再部署生产

---

## 附录：为什么任务是串行而非并发？

### 设计决策

当前管理后台的任务执行是**按任务类型（kind）串行**：同一时刻只允许一个 `summarize` 任务运行，但不同类型（如 `summarize` + `crawl`）可以同时执行。

### 为什么选择串行？

1. **数据一致性**：
   - `summarize` 任务读取 `posts` 表生成总结，并发执行可能读到不一致的中间状态
   - `stock_sync` 全市场同步会写 `stock_daily` 表，并发可能导致主键冲突或数据覆盖

2. **资源保护**：
   - 单个 `summarize` 任务可能调用 LLM API 几十次（每个大V + 每种类型）
   - 并发执行会打爆 LLM API 配额（OpenAI Tier 1：10K tokens/min）或触发 rate limit
   - Celery `llm` 队列的 worker 数量有限（通常 1-2 个），并发任务会在队列中排队而非真正并行

3. **任务特性差异**：
   - **Java 后台任务**：细粒度（单个用户操作）、秒级执行、高并发场景适合线程池
   - **当前系统任务**：粗粒度（全站数据同步/全部大V总结）、分钟到小时级、低频手动触发

4. **实际需求**：
   - 管理员手动触发频率极低（一天几次）
   - 定时任务已通过 Celery beat 调度，不需要手动并发触发
   - 当前无"多个运营同时操作"的并发场景

### 并发改造的成本与风险

如果未来需要支持并发（如：10 个运营同时给不同大V生成总结），需要：

**技术改造**：
1. 实现细粒度锁（按任务参数去重，允许不同参数的任务并发）
2. `job_runs` 表增加 `params` 列（JSON 类型）存储任务参数
3. Alembic 迁移脚本添加列并建立索引

**资源评估**：
1. LLM API 配额是否支持并发（需升级到更高 tier 或换成自部署模型）
2. Celery worker 数量增加（当前 `llm` 队列可能只有 1 个 worker）
3. 数据库连接池扩容（当前 `pool_size=5`，并发任务会快速耗尽）

**风险**：
1. 总结任务非幂等（重复生成会覆盖旧版本），并发可能导致数据混乱
2. LLM API rate limit 触发后，所有任务失败需重试
3. 数据库连接池耗尽导致整个 API 不可用

### 结论

**保持当前串行设计**，除非出现以下明确需求之一：
- 多个管理员需要同时触发不同参数的任务（如：同时生成 10 个大V 的总结）
- 单个任务执行时间过长（> 1 小时），导致其他任务长时间等待
- LLM API 配额充足（如：自部署模型无限制调用）

当前的"僵尸任务自动清理"机制已足够应对 worker 崩溃等异常情况，无需引入并发带来的额外复杂度。
