# 雪球大V看板 & A股选股系统 —— 服务化重构技术方案与 Phase 1 交付报告

| 项 | 内容 |
|---|---|
| 文档类型 | 技术方案（Design Doc）+ 阶段交付报告 |
| 版本 | v1.0 |
| 状态 | Phase 1 已交付并验收通过；Phase 2 待启动 |
| 更新日期 | 2026-07-08 |
| 涉及模块 | 后端服务化、数据迁移、公开只读 API、缓存、容器化 |
| 关联代码 | `backend/`（新）、根目录旧 Flask 工具（保留） |

---

## 0. TL;DR

将一个**单机个人工具**（Flask + SQLite + 原生 JS，进程内线程跑后台任务）重构为**可支撑千人并发只读访问的服务化架构**（FastAPI + PostgreSQL + Redis + 分布式队列，Docker Compose 编排）。采用**分阶段**推进，本次交付 **Phase 1（后端地基）**：完成数据层迁移（520 万行）、全部公开只读接口、缓存层与容器化，并通过**新旧接口逐字节对拍验收（16/16）**。旧系统保持可运行，作为对拍基准与回退方案。

---

## 1. 背景与问题（Why）

现有系统是面向单人本地使用的工具，两条业务主线：

1. **雪球大V帖子抓取 + AI 总结**（日/周/月/年分层归并 + 精华帖 + 配图视觉识别）；
2. **A股行情/财务/板块数据 + 选股筛选看板**（预设策略、技术指标、板块/大V提及过滤、个股详情K线）。

在"上线、千人并发"的新诉求下，原架构存在结构性瓶颈：

| 维度 | 现状 | 上线后的问题 |
|---|---|---|
| Web 框架 | Flask 同步 + `threaded=True` | 同步阻塞模型，高并发下线程资源紧张 |
| 存储 | SQLite 单文件 | 单写者、无连接池、无法多实例共享 |
| 后台任务 | 进程内 daemon 线程 + 内存状态字典 + 轮询 | 与 Web 进程强耦合，重启即丢状态，无法横向扩展 |
| 缓存 | 无 | 选股全表扫描（5500 股 × 90 天）每次请求现算，扛不住并发 |
| 配置/鉴权 | `.env` + `schedule.json`，无鉴权 | 全局单用户模型，无法区分公开读者与管理员 |

**结论**：并发压力集中在**读侧**（看板/总结/选股/K线浏览），而数据采集侧（依赖真实浏览器抓雪球、回补K线）本质是**单节点后台管线**。因此重构主线是"异步读接口 + 队列化 worker + 共享数据源 + 重缓存"，而非"把抓取扩到 1000×"。

---

## 2. 目标与非目标（Goals / Non-Goals）

**目标**
- G1：读接口可横向扩展、支撑千人并发（异步 + 缓存 + 连接池）。
- G2：存储迁移到 PostgreSQL，历史全量数据零丢失。
- G3：后台任务与 Web 解耦（分布式队列），状态可持久化观测。
- G4：确立"只读公开 + 管理员后台"权限模型。
- G5：重构过程可灰度、可回退，行为与旧系统对齐（对拍验收）。

**非目标（本轮不做）**
- N1：不改变业务算法（选股策略、指标公式、总结分层逻辑逐字沿用）。
- N2：不追求 Kubernetes / 多云；起步用 Docker Compose 单机。
- N3：不做每用户数据隔离（公开读者匿名，无个人自选/关注列表）。
- N4：不重写抓取方案（真实 Edge + 登录态仍是唯一可靠通道）。

---

## 3. 关键设计决策（Decision Log）

| 决策 | 选择 | 依据 |
|---|---|---|
| 用户模型 | **只读公开 + 管理员后台** | 千人是读者；仅管理员配置大V/触发采集。公开读匿名 ⇒ 可激进缓存，无租户隔离成本 |
| Web 框架 | **FastAPI（异步）** | 原生 async、依赖注入、OpenAPI；异步模型下"并发≠连接数"，配缓存后单实例即可扛高并发 |
| 数据库 | **PostgreSQL 16** | 多写者、连接池、成熟运维生态；`ON CONFLICT` 精确复刻旧 upsert 语义 |
| 缓存/中间件 | **Redis 7** | 读缓存 + 后续队列 broker + 限流；dataver 版本号一次 INCR 全失效，热路径无 SCAN |
| 分布式队列 | **Celery + Redis** | 采集/同步/总结解耦为任务；专用队列隔离浏览器任务 |
| 前端（Phase 4） | **React + Vite + TS + Ant Design + TanStack Query + ECharts** | 纯数据看板 + 图表 + 表单筛选；AntD 为国内大厂中后台事实标准 |
| 部署 | **Docker Compose 单机** | 起步成本低，后续可平滑迁 K8s |
| 迁移策略 | **新旧并行 + 逐字节对拍** | 降低回归风险；旧系统作基准与回退 |

**决策要点：异步/同步分界**
轻量读（帖子、总结、看板）走 asyncpg 异步会话；选股/K线等**CPU 密集且从旧代码逐字移植**的同步逻辑，跑在 `run_in_threadpool` + 独立小同步连接池 —— 既保住并发，又保证移植逻辑不走样（对拍是验收闸门）。

---

## 4. 目标架构

```
                         ┌───────────────────────────────┐
   千人并发读者  ─────▶  │      Nginx / 反向代理 (P4)     │
   (匿名浏览)            └───────────────┬───────────────┘
                                         │
                    ┌────────────────────┴───────────────────┐
                    │            FastAPI (可多实例)            │
                    │  公开只读路由        管理员路由(鉴权 P3) │
                    │  异步会话──轻量读    threadpool──重计算  │
                    └───────┬─────────────────────┬───────────┘
                            │                      │
              ┌─────────────▼───────┐   ┌──────────▼─────────┐
              │      Redis          │   │    PostgreSQL 16    │
              │  读缓存 / broker    │   │  行情·帖子·总结·板块 │
              │  限流 / 任务状态    │   │  (连接池 + 索引)     │
              └─────────────▲───────┘   └──────────▲─────────┘
                            │ 任务/结果            │ 读写
        ┌───────────────────┴──────────┐          │
        │        Celery Workers         │          │
        │  ┌────────────┐ ┌───────────┐ │          │
        │  │ 容器化 队列 │ │ 宿主 队列  │─┼──────────┘
        │  │ 快照/财务/  │ │ browser:   │ │   (Windows 宿主，真实 Edge)
        │  │ 板块/总结   │ │ 抓取/回补  │ │
        │  └────────────┘ └───────────┘ │
        └───────── Celery Beat 定时 ─────┘
        （虚线框内为 Phase 2 交付；实线为 Phase 1 已就位）
```

**关键约束 —— 浏览器任务不可容器化**
雪球抓取与 K线回补依赖 **可见的真实 Edge + 持久化登录态 + 人工过滑块**，无法在 headless Linux 容器运行。方案：预留专用队列 `QUEUE_BROWSER`，由 **Windows 宿主 worker** 消费（连 Compose 发布出来的 DB/Redis 端口）；其余纯 `requests` 型同步与 LLM 总结跑容器化 worker。`scraper.py` 刻意不进 API 镜像。

---

## 5. 数据模型与迁移

### 5.1 表结构
镜像旧 SQLite 8 张表（`posts`/`summaries`/`stock_daily`/`stock_finance`/`stock_groups`/`stock_group_members`/`sector_catalog`/`stock_sector`），列/约束/索引逐字复刻；新增 3 张管理表：

| 新表 | 用途 | 取代 |
|---|---|---|
| `xueqiu_users` | 管理员维护的大V采集名单 | 旧 `.env` 的 `XUEQIU_USERS` |
| `schedules` | 自动采集窗口配置 | 旧 `data/schedule.json` |
| `job_runs` | 后台任务状态/日志 | 旧进程内内存状态字典 |

类型映射保持机械可迁移（TEXT→String、epoch INTEGER→BigInteger、REAL→Double）；`stock_daily` 以 `(trade_date, code)` 作复合主键（旧表原为 UNIQUE 自然键），避免在 520 万行上多挂序列。

### 5.2 迁移工程
| 指标 | 值 |
|---|---|
| 源库体积 | 700 MB |
| `stock_daily` 行数 | **5,214,370** |
| 迁移方式 | psycopg3 **流式 COPY**，`fetchmany(50k)` 分批，绝不整表进内存 |
| 加速手段 | COPY 前 drop 索引、载完重建 |
| 幂等 | `--truncate` 支持重跑；默认拒绝写入非空表 |
| 全量耗时 | **≈68 秒** |
| upsert 语义 | 旧 `INSERT OR REPLACE/IGNORE` → PG `ON CONFLICT`（含 `save_history_bars` 的"只补空 open"逻辑） |

---

## 6. 分阶段路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| **Phase 1** | 后端地基：FastAPI 骨架、Postgres+Alembic、数据迁移、全部公开只读接口、Redis 缓存、容器化 | ✅ **已交付** |
| Phase 2 | Celery + 队列：容器化 worker（快照/财务/板块/总结）+ 宿主 worker（抓取/回补）；Beat 定时；`job_runs` 状态接口；激活管理员写接口 | ⏳ 待启动 |
| Phase 3 | 管理员 JWT 鉴权（新增 `admins` 表）+ 限流 | 规划中 |
| Phase 4 | React+Vite+TS+AntD 前端重写；Nginx 托管 | 规划中 |
| Phase 5 | 硬化：预计算指标表消除全表扫描、PgBouncer、可观测性、备份、CI/CD | 规划中 |

---

## 7. Phase 1 交付清单与验收

### 7.1 交付物
- **服务骨架**：应用工厂 + lifespan + CORS + `/health`；pydantic-settings 配置（1:1 复刻旧 `config.py`）。
- **数据层**：异步引擎（asyncpg，连接池 20+10）+ 同步引擎（重计算专用）；11 张 ORM 模型；Alembic 初始迁移。
- **迁移工具链**：`migrate_sqlite_to_pg.py` / `verify_migration.py` / `parity_check.py`。
- **14 个公开只读接口**（响应体与旧 Flask 逐字节对齐）：

  `/api/users`·`/api/overview`·`/api/posts`·`/api/summary_keys`·`/api/summary`·`/api/screen/fields`·`/api/screen/sectors`·`POST /api/screen`·`POST /api/screen/preset`·`/api/stock/kline`·`/api/stock/fundamentals`·`/api/stock/news`·`/api/groups`·`/api/groups/{id}/members`
- **缓存层**：Redis + dataver 版本号失效，覆盖 overview/posts/summary/screen/kline/fundamentals/sectors/news。
- **管理员接口占位**：全部返回 501，提前锁定 URL 契约。
- **队列占位**：`celery_app` + `queues`（`QUEUE_DEFAULT/BROWSER/LLM`）。
- **容器化**：`docker-compose.yml`（postgres/redis/api）+ `Dockerfile`（非 root，镜像不含 Playwright）。

### 7.2 验收结果
| 验收项 | 结果 |
|---|---|
| Alembic 建表（11 表 + 索引） | ✅ |
| 数据迁移 520 万行 | ✅ 68s |
| 迁移校验（逐表计数 + 聚合抽查） | ✅ 全绿 |
| 本地 API + 容器 API 出数 | ✅ |
| 新旧接口对拍 | ✅ **16/16** |
| 管理员接口 501 | ✅ |

> 对拍中 2 项标记"顺序不同但内容一致"：中文名在 PG 与 SQLite 不同排序规则（collation）下顺序有别、以及 `change_pct` 相等时的并列顺序差异 —— 内容完全一致，不影响正确性，可由前端或后续显式 `ORDER BY` 收敛。

---

## 8. 质量保障与验证

- **对拍验收（黄金标准）**：`scripts/parity_check.py` 自发现测试参数，对固定接口矩阵逐一比较新旧 JSON，浮点按容差、无序列表退化为集合比较。这是"忠实移植"的验收闸门。
- **迁移校验**：计数 + `MAX(created_at)`/`SUM(like_count)`/`COUNT(DISTINCT code)` 等聚合抽查，任何不一致非零退出。
- **移植保真原则**：`repositories/sync_data.py` 为旧 `db.py` 同步近似复刻，返回 dict 键与旧 `sqlite3.Row` 完全一致，使 `stock.py` 业务逻辑近乎逐字复用。
- **灰度与回退**：新旧系统并行，旧 Flask+SQLite 在前端切换（Phase 4）前不动。

---

## 9. 容量与性能考量（千人并发）

- **并发模型**：FastAPI 异步下"请求 await 不占连接"，连接池 20~30 足够；热点读全部命中 Redis，DB 仅承接缓存未命中的短查询。**不把连接池开到接近 1000**；若后续压测出现池饱和，引入 PgBouncer（事务级池化）而非放大池。
- **最大热点 —— 选股全表扫描**：`screen_*` 需拉全量历史并循环 5500×90，是 CPU 密集路径。Phase 1 用 threadpool + 硬缓存（TTL 180s）兜住"相同筛选"的重复请求；**根治方案（Phase 5）**为夜间预计算指标表 / 物化视图，把请求期计算降为一次索引查询。
- **缓存失效**：数据同步（Phase 2）末尾调用 `cache.invalidate_all()` = 一次 `INCR natapp:dataver`，旧 key 立即不可达并靠 TTL 过期，避免 `KEYS/SCAN` 扫描。

---

## 10. 风险、假设与遗留问题

| 项 | 说明 | 缓解 |
|---|---|---|
| 选股高并发 | 大量**不同**筛选仍会击穿缓存做全表扫描 | Phase 5 预计算指标表；必要时限流 |
| 浏览器任务单点 | 抓取/回补依赖单台 Windows 宿主 + 人工过滑块 | 独立 `QUEUE_BROWSER`；失败重试 + 去重补抓 |
| 外部数据源不稳 | 新浪/东财接口偶发限流、GBK 编码、host 被墙 | 逐项 try/except、超时、缓存挡上游（沿用旧经验） |
| 跨库排序差异 | 中文 collation 导致列表顺序不同 | 内容一致；关键列表显式 `ORDER BY` 或前端排序 |
| 基础设施单点 | 单机 Compose，DB/Redis 无副本 | Phase 5 备份 + 迁 K8s；先做定期快照 |
| 中转站/密钥 | LLM 总结依赖中转站可用性 | 密钥只留 env；总结走队列异步，失败不阻塞读 |

**环境适配（已知）**：本机另有一套微服务栈占用 5432/6379/8000，本项目容器改用 **5433 / 6380 / 8088**；换干净机器时改回默认即可。docker.io 拉基础镜像偶发超时，重试可成功。

---

## 11. 附录

### A. 目录结构
```
backend/
  app/
    core/         config / db(异步) / sync_db(同步) / cache / markdown
    models/       11 张表模型
    repositories/ 异步读仓储 + sync_data(同步)
    services/     indicators/screening/matching/views/screen_api/overview + external/sina
    api/routers/  public(只读) + admin(占位 501)
    workers/      celery_app / queues(占位)
  alembic/        迁移
  scripts/        migrate_sqlite_to_pg / verify_migration / parity_check
  docker-compose.yml  Dockerfile  requirements.txt  requirements-host.txt
```

### B. 端口约定（本机）
| 服务 | 容器内 | 宿主 |
|---|---|---|
| PostgreSQL | 5432 | 5433 |
| Redis | 6379 | 6380 |
| API | 8000 | 8088 |

### C. 运行手册（速查）
```bash
cd backend
docker compose up -d postgres redis            # 起数据库/缓存
./.venv/Scripts/python -m alembic upgrade head # 建表
./.venv/Scripts/python -m scripts.migrate_sqlite_to_pg --sqlite ../data/posts.db --truncate
./.venv/Scripts/python -m scripts.verify_migration --sqlite ../data/posts.db
docker compose up -d --build api               # 起 API → http://127.0.0.1:8088
```
对拍：旧 Flask `python main.py serve --port 5000` + 新 API，再跑 `scripts/parity_check.py`。

### D. 名词
- **dataver**：Redis 里的全局数据版本号，缓存 key 内嵌其值，同步后 +1 即整体失效。
- **对拍（parity check）**：以旧系统为基准，逐接口比较新系统输出的一致性验证方法。

---

*本报告随重构推进滚动更新；Phase 2 启动后追加"队列与任务"章节及压测数据。*
