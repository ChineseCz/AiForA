# Bug修复与任务执行机制说明

**Phase**：Phase 17  
**日期**：2026-08-19  
**提交范围**：`d2c63a4` ~ `430093a`  
**类型**：Bug修复 + 架构说明文档

---

## 修复内容概述

### 问题
管理后台"生成AI总结"按钮点击无响应，任务未执行。

### 根本原因
1. **僵尸任务阻塞**：21天前的手动任务因 worker 崩溃/异常退出，永久停留在 `status=running` 状态
2. **无超时清理机制**：`any_running()` 简单检查数据库记录，无超时自动清理
3. **前端反馈不明确**：阻塞时仅显示 `message.info("任务已在运行中")`，未区分正常排队与异常阻塞

### 解决方案

#### 1. 后端自动清理超时任务
**文件**：`backend/app/repositories/jobs.py`

在 `any_running()` 检查前，自动清理 `started_at` 距今超过 2 小时且仍为 `running` 的任务：

```python
async def any_running(session: AsyncSession, kind: str) -> bool:
    """检查是否有正在运行的任务，自动清理超时僵尸任务（超过 2 小时未完成视为异常）。"""
    now = int(time.time())
    timeout_seconds = 2 * 3600  # 2 小时

    # 先清理僵尸任务
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

#### 2. 后端返回明确错误信息
**文件**：`backend/app/api/routers/admin/jobs.py`

阻塞时返回 `error` 字段说明原因：

```python
if await jobs.any_running(session, "summarize"):
    return {"started": False, "running": True, "error": "已有任务正在运行，请稍后再试"}
```

#### 3. 前端警告提示
**文件**：`frontend/src/pages/Admin.tsx`

改用 `message.warning()` + 显示后端返回的具体原因：

```typescript
// JobPanel 和 JobPanelInline 统一改为：
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
```

---

## 部署步骤

### 服务器端清理僵尸任务（必须先执行）

```bash
# 连接服务器 PostgreSQL
docker exec -it <postgres容器名> psql -U <用户名> -d <数据库名>

# 清理所有超过 2 小时的僵尸任务
UPDATE job_runs 
SET status='error', 
    finished_at=EXTRACT(EPOCH FROM NOW())::INTEGER, 
    error='任务超时，手动清理' 
WHERE status='running' 
  AND started_at < EXTRACT(EPOCH FROM NOW())::INTEGER - 7200;

# 查看清理了多少条
SELECT kind, COUNT(*) 
FROM job_runs 
WHERE status='error' AND error='任务超时，手动清理' 
GROUP BY kind;
```

### 部署新代码

```bash
git pull
docker compose restart api worker
docker compose up -d --build frontend
```

---

## 任务执行机制说明

### 为什么任务是串行而非并发？

当前管理后台的任务执行是**按任务类型（kind）串行**：同一时刻只允许一个 `summarize` 任务运行，但不同类型（如 `summarize` + `crawl`）可以同时执行。

### 串行设计的原因

#### 1. 数据一致性
- `summarize` 任务读取 `posts` 表生成总结，并发执行可能读到不一致的中间状态
- `stock_sync` 全市场同步会写 `stock_daily` 表，并发可能导致主键冲突或数据覆盖

#### 2. 资源保护
- 单个 `summarize` 任务可能调用 LLM API 几十次（每个大V + 每种类型）
- 并发执行会打爆 LLM API 配额（OpenAI Tier 1：10K tokens/min）或触发 rate limit
- Celery `llm` 队列的 worker 数量有限（通常 1-2 个），并发任务会在队列中排队而非真正并行

#### 3. 任务特性差异

| 维度 | Java 线程池后台任务 | 当前 Celery 任务 |
|-----|-------------------|----------------|
| **任务粒度** | 细粒度（单个用户操作） | 粗粒度（全站数据同步/全部大V总结） |
| **执行时间** | 秒级（发邮件/推送通知） | 分钟到小时级（采集几千条帖子） |
| **触发频率** | 高频（每秒几百次） | 低频（管理员手动触发，一天几次） |
| **并发需求** | 必须并发（用户体验） | 无需并发（单次执行足够） |
| **幂等性** | 通常幂等（重试安全） | 部分非幂等（总结生成会覆盖旧版本） |

#### 4. 实际需求
- 管理员手动触发频率极低（一天几次）
- 定时任务已通过 Celery beat 调度，不需要手动并发触发
- 当前无"多个运营同时操作"的并发场景

### 并发改造的成本与风险

如果未来需要支持并发（如：10 个运营同时给不同大V生成总结），需要：

#### 技术改造
1. **实现细粒度锁**：按任务参数去重，允许不同参数的任务并发
2. **数据库改造**：`job_runs` 表增加 `params` 列（JSON 类型）存储任务参数
3. **迁移脚本**：Alembic 添加列并建立索引

#### 资源评估
1. **LLM API 配额**：是否支持并发（需升级到更高 tier 或换成自部署模型）
2. **Celery worker**：数量增加（当前 `llm` 队列可能只有 1 个 worker）
3. **数据库连接池**：扩容（当前 `pool_size=5`，并发任务会快速耗尽）

#### 风险
1. **数据混乱**：总结任务非幂等（重复生成会覆盖旧版本），并发可能导致数据混乱
2. **API限流**：LLM API rate limit 触发后，所有任务失败需重试
3. **服务不可用**：数据库连接池耗尽导致整个 API 不可用

### 结论

**保持当前串行设计**，除非出现以下明确需求之一：
- 多个管理员需要同时触发不同参数的任务（如：同时生成 10 个大V 的总结）
- 单个任务执行时间过长（> 1 小时），导致其他任务长时间等待
- LLM API 配额充足（如：自部署模型无限制调用）

当前的"僵尸任务自动清理"机制已足够应对 worker 崩溃等异常情况，无需引入并发带来的额外复杂度。

---

## 验证方案

### 1. 僵尸任务自动清理
1. 手动插入一条超时任务：
```sql
INSERT INTO job_runs (kind, status, source, log, error, started_at, finished_at)
VALUES ('summarize', 'running', '测试', '', '', EXTRACT(EPOCH FROM NOW())::INTEGER - 10000, NULL);
```

2. 点击"生成AI总结"按钮

3. 预期结果：
   - 后端自动清理僵尸任务（标记为 `error`）
   - 新任务正常创建并执行
   - 前端提示"已触发"

### 2. 真实并发阻塞
1. 启动一个真实的长时间任务（如全量总结）
2. 在其运行时再次点击按钮
3. 预期结果：前端显示**黄色警告**"已有任务正在运行，请稍后再试"

---

## 后续优化建议（可选）

### 1. Celery 任务侧兜底
检查所有长时间任务是否都使用了 `@job_context` 装饰器，保证无论成功失败都调用 `finish_job()`。

### 2. 管理后台增加"任务列表"页
显示最近 50 条 `job_runs` 记录，允许管理员：
- 查看每个任务的启动时间、耗时、日志
- 手动强制终止僵尸任务

### 3. 监控告警
- Prometheus + Grafana 监控 `job_runs` 表中 `status=running` 且 `started_at < now - 1小时` 的记录数
- 超过阈值时发送告警

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
- 架构清晰：明确了"串行执行"的设计决策及原因

**修改文件**：
- `backend/app/repositories/jobs.py`：新增超时清理逻辑
- `backend/app/api/routers/admin/jobs.py`：返回 `error` 字段
- `frontend/src/pages/Admin.tsx`：改用 `warning` 提示
