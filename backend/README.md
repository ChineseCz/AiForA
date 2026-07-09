# natapp 后端（FastAPI 重构 · Phase 1）

把旧的单机 Flask + SQLite 工具重构为可上线的 FastAPI + Postgres + Redis 架构。
**用户模型**：只读公开 + 管理员后台（公开读者匿名、可重缓存；写/触发操作限管理员，Phase 2/3 启用）。
**部署**：Docker Compose 单机。

## 本机端口约定（重要）
本机已跑着另一套微服务栈，占用了 5432/6379/8000。为避免冲突，本项目容器**改用**：

| 服务 | 容器内 | 宿主发布 |
|---|---|---|
| Postgres | 5432 | **5433** |
| Redis | 6379 | **6380** |
| API | 8000 | **8088** |

`backend/.env` 里的 `DATABASE_URL`/`REDIS_URL` 已指向 5433/6380（本地开发直连宿主端口）。
换到没有冲突的机器时，把 `docker-compose.yml` 的端口映射和 `.env` 改回默认即可。

## 目录结构
```
backend/
  app/
    core/        config(pydantic-settings) / db(异步引擎) / sync_db(重计算同步引擎) / cache(Redis) / markdown
    models/      11 张表的 SQLAlchemy 模型（8 张镜像旧库 + xueqiu_users/schedules/job_runs）
    repositories/ 异步读仓储(posts/summaries/sectors/groups) + sync_data(同步，供选股/K线计算)
    services/    indicators/screening/matching/views/screen_api/overview + external/sina
    api/routers/ public(只读) + admin(占位 501)
    workers/     celery_app/queues(占位，Phase 2 启用)
  alembic/       迁移（0001 初始建表）
  scripts/       migrate_sqlite_to_pg / verify_migration / parity_check
  docker-compose.yml  Dockerfile  requirements.txt  requirements-host.txt
```

## 首次跑起来（本地开发）
```bash
cd backend
python -m venv .venv && ./.venv/Scripts/python -m pip install -r requirements.txt

# 1. 起数据库/缓存
docker compose up -d postgres redis

# 2. 建表
./.venv/Scripts/python -m alembic upgrade head

# 3. 迁移旧 SQLite 数据（700MB / 520 万行，约 1 分钟）
./.venv/Scripts/python -m scripts.migrate_sqlite_to_pg --sqlite ../data/posts.db --truncate

# 4. 校验迁移
./.venv/Scripts/python -m scripts.verify_migration --sqlite ../data/posts.db

# 5a. 本地起 API
./.venv/Scripts/python -m uvicorn app.main:app --port 8010
# 5b. 或用容器起 API（连 compose 网络内的 pg/redis）
docker compose up -d --build api   # → http://127.0.0.1:8088
```

## 对拍验证（vs 旧 Flask）
```bash
# 终端1：旧 Flask（项目根，用其自带 venv）
python main.py serve --port 5000
# 终端2：新 API（见上）
# 终端3：
cd backend && ./.venv/Scripts/python -m scripts.parity_check --old http://127.0.0.1:5000 --new http://127.0.0.1:8010
```
Phase 1 实测 16/16 通过（两处「顺序不同但内容一致」：中文名在 PG/SQLite 不同排序规则下顺序有别、
以及 change_pct 相等时的并列顺序——内容完全一致，不影响正确性）。

## Phase 1 已实现的公开只读接口
`/api/users` `/api/overview` `/api/posts` `/api/summary_keys` `/api/summary`
`/api/screen/fields` `/api/screen/sectors` `POST /api/screen` `POST /api/screen/preset`
`/api/stock/kline` `/api/stock/fundamentals` `/api/stock/news`
`/api/groups` `/api/groups/{id}/members`

所有响应体与旧 Flask 逐字节对齐（读接口刻意返回原生 dict，不套 Pydantic 响应模型）。
重计算（选股/K线/基本面）跑在 `run_in_threadpool` + 同步会话；热路径全部走 Redis 缓存
（dataver 版本号失效策略）。

## 关键设计决策
- **异步/同步分界**：轻量读走 asyncpg 异步会话；选股/K线等重计算是 ported 的同步逻辑，
  跑 threadpool + 小同步池，保持逻辑逐字不变（对拍是验收闸门）。
- **忠实移植**：`repositories/sync_data.py` 是旧 `db.py` 的同步近似复刻；`services/*` 逐字移植
  自 `stock.py`。upsert 用 Postgres `ON CONFLICT`（含 `save_history_bars` 的「只补空 open」语义）。
- **浏览器任务隔离**：抓取 / K线回补依赖真实可见 Edge，无法容器化 → 预留 `QUEUE_BROWSER`，
  Phase 2 由 **Windows 宿主 worker** 消费（连 compose 发布出来的 5433/6380）。`scraper.py` 不进镜像。
- **缓存失效**：数据同步（Phase 2）末尾调 `cache.invalidate_all()` = 一次 `INCR natapp:dataver`，
  旧 key 立即不可达 + TTL 过期，热路径无 SCAN/KEYS。

## Phase 2 已实现（分布式队列 + 后台任务 + 管理员写接口）
- **Celery + Redis**：`app/workers/` 定义 9 个任务，三条队列：
  - `default`（容器化）：`stock.sync_snapshot` / `finance_sync` / `sector_catalog` / `sector_members`
  - `llm`（容器化）：`summarize.run` / `summarize.daily_one`
  - `browser`（**Windows 宿主专用**）：`browser.crawl` / `browser.backfill`（真实 Edge，见下）
- **job_runs 表 + 状态接口**取代旧内存字典轮询：触发接口**预建 running 行再入队**，使 `running` 入队即可见（消除轮询竞态）；任务 stdout 实时捕获进 `job_runs.log`。
- **Celery beat**：每 60s 一次 `beat.tick`，读 `schedules` 表决定是否派发采集（取代旧内置 20s 轮询线程），Redis SETNX 做同槽位去重。
- **缓存失效**：数据同步任务成功后 `bump_dataver_sync()`（一次 INCR），读缓存整体失效。
- **管理员写接口已激活**（501 → 实装）：`/api/crawl*` `/api/summarize*` `/api/summary/ask` `/api/stock/sync*` `/api/stock/backfill*` `/api/stock/finance_sync*` `/api/stock/sync-sectors*` `/api/stock/sync-sector-members*` `GET|POST /api/schedule` `POST/DELETE /api/groups*`。

### 启动 worker / beat
```bash
# 容器化（default + llm 队列）—— 已在 docker-compose.yml
docker compose up -d worker beat

# 浏览器队列 worker —— 必须在 Windows 宿主运行（真实 Edge + 登录态，无法容器化）
cd backend && ./.venv/Scripts/python -m pip install -r requirements-host.txt
./.venv/Scripts/python -m celery -A app.workers.celery_app worker -Q browser --pool=solo --loglevel=info
# 首次抓取前需登录一次雪球（宿主执行）：
./.venv/Scripts/python -c "from app.scrapers.xueqiu import login; login()"
```

### Phase 2 验收（已通过）
容器化路径端到端实测：触发 `/api/stock/sync-sectors` → `running:true` 入队即可见 → 容器 worker 拉取新浪 259 板块写库 → `job_runs` 记 `done` + 日志 → `dataver` 递增（缓存失效）。schedule GET/POST、分组 CRUD、beat 每 60s tick 均验证通过。
> 浏览器队列（crawl/backfill，需真实 Edge+登录）与 LLM 队列（summarize/ask，需 `RELAY_API_KEY`）代码已移植并接线，因本机无对应运行条件未做真机执行验证。

## Phase 3 已实现（管理员鉴权 + 限流）
- **JWT 鉴权**：`admins` 表（migration 0002）+ bcrypt 密码哈希 + PyJWT（HS256）。
  - `POST /api/admin/login` → 返回 `access_token`；`GET /api/admin/me` 校验登录态。
  - 所有 `admin/` 写/触发路由挂 `require_admin` 守卫（`Authorization: Bearer <token>`），无/坏 token → 401。
  - 公开只读路由保持匿名开放。
- **启动引导管理员**：`admins` 表空且配置了 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 时自动建号；生产改用 `python -m scripts.create_admin --username x --password y`（避免密码进 env）。
- **限流**：slowapi + **Redis 存储**（多 API 实例共享计数，横向扩展前提）。公开接口默认 `120/min`（按 IP），登录接口 `5/min`（防爆破），超限返回 429。

配置（`.env`）：`JWT_SECRET`（生产必须强随机）、`JWT_EXPIRE_MINUTES`（默认 720）、`ADMIN_USERNAME`/`ADMIN_PASSWORD`、`RATE_LIMIT_PUBLIC`/`RATE_LIMIT_LOGIN`。

### Phase 3 验收（已通过）
无 token 调管理员接口→401；公开接口→200；错误密码登录→401；正确登录→JWT；带 token 调管理员接口→200；坏 token→401；登录 5 次/分钟后→429；公开接口不受登录限额影响。

## Phase 4 已实现（前端重写）
- **React + Vite + TS + Ant Design + TanStack Query + ECharts**，代码在 `frontend/`。
- 页面：看板（统计卡 + 发帖日历热力 + 月度柱状 + 最新动态）、帖子流（Table + 日期/关键词/大V过滤 + 分页）、AI总结（周期 tabs + key 列表 + markdown 渲染 + 向AI提问）、选股（预设策略 + 条件构建 + 提及/板块过滤 + 结果表→详情）、个股详情（蜡烛图 + MA/成交量/MACD/KDJ 四联动 + 买卖点标记 + 基本面/板块/提及/新闻）、管理后台（登录 + 各同步触发与状态轮询 + 定时配置 + 总结生成）。
- **鉴权**：JWT 存 localStorage，axios 拦截器自动附带，401 自动登出，`/admin` 路由守卫。
- **Nginx 托管**：多阶段构建（Node 构建 → nginx），同源反代 `/api`→`api:8000`（免 CORS），SPA history 回退。compose 新增 `frontend` 服务（宿主 8090）。

### Phase 4 验收（已通过）
`npm run build` 类型检查+构建通过；容器化 nginx 出 SPA、深路由回退 200、`/api` 同源代理（GET/POST/带 JWT）全通。访问 `http://localhost:8090`。

## 全栈一览（docker compose，6 服务）
`postgres(5433) · redis(6380) · api(8088) · worker · beat · frontend(8090)`；浏览器队列 worker 另在 Windows 宿主跑。

## Phase 5 已实现（硬化）
- **预计算指标表 `stock_indicator`（migration 0003）**：把选股里"拉全量历史 + 循环 5500×90"的现算，改为数据更新后 worker 预计算一次落表；选股请求直接读表。快路径与现算**结果集与顺序完全一致**，实测 15~25× 提速（0.07~0.12s vs 1.8~2.1s，且并发下差距更大）。快照/回补任务完成后自动 `recompute_indicators`；表未就绪时自动回退现算，正确性不依赖预计算。
- **可观测性**：`/ready`（探活 Postgres+Redis，任一挂→503）、`/metrics`（Prometheus，prometheus-fastapi-instrumentator）。
- **PgBouncer**：事务级连接池服务（收敛真实 PG 连接数，横向扩展护栏）。asyncpg 经事务池已设 `statement_cache_size=0`；实测经 6432 查询通。默认不强制走，启用时把 `DATABASE_URL` 主机改 `pgbouncer:5432`。
- **备份**：`scripts/backup.sh`（pg_dump→gzip，保留最近 14 份），配 Windows 任务计划/cron 每日跑。
- **CI**：`.github/workflows/ci.yml`（后端 ruff+import 检查、前端 npm build、docker build）。
- **前端 code-split**：vite manualChunks 拆 echarts/antd/react vendor chunk（并行加载 + 独立缓存）。

## 全栈一览（docker compose，7 服务）
`postgres(5433) · pgbouncer(6432) · redis(6380) · api(8088) · worker · beat · frontend(8090)`；浏览器队列 worker 另在 Windows 宿主跑。

五阶段（读接口地基 → 队列/worker → 鉴权/限流 → 前端 → 硬化）已全部落地。旧 Flask + SQLite 仍保留，可作对拍/回退。
```
