# 项目速览（写给下一次会话的 Claude）

雪球大V帖子抓取+AI总结 & A股行情/财务/板块+选股 的系统。**本分支（release_v2）是服务化新架构**：
前后端分离，面向千人并发只读访问。旧的单机版（Flask + SQLite + 原生JS）保留在 **release_v1** 分支，
本分支已移除其代码。改动后靠 docker compose 起栈 + 对拍/curl/浏览器验证（无强制测试框架）。

## 架构与技术栈

- **后端 `backend/`（FastAPI）**：异步 SQLAlchemy 2.0(asyncpg) 轻量读 + 同步引擎(psycopg)跑重计算(选股/K线，`run_in_threadpool`)。
- **PostgreSQL**：主库（migration 见 `backend/alembic/`，0001 建 11 表，0002 admins，0003 预计算指标表）。
- **Redis**：读缓存（dataver 版本号失效）+ Celery broker + slowapi 限流存储。
- **Celery**：9 任务 / 3 队列 —— `default`/`llm` 容器化 worker；`browser`（雪球抓取 + K线回补，依赖真实 Edge）**只能在 Windows 宿主 worker 跑**。beat 每 60s 读 `schedules` 表决定采集。
- **PgBouncer**：事务级连接池（asyncpg 需 `statement_cache_size=0`，已设）。
- **前端 `frontend/`（React+Vite+TS+Ant Design+TanStack Query+ECharts）**：6 页面；Nginx 多阶段构建 + 同源反代 `/api`。

## 目录职责（backend/app）

| 路径 | 职责 |
|---|---|
| `core/` | config(pydantic-settings) / db(异步引擎) / sync_db(同步引擎) / cache(Redis+dataver) / security(JWT+bcrypt) / ratelimit(slowapi) / markdown / bootstrap(引导管理员) |
| `models/` | 12 张表的 ORM（8 张镜像旧库 + xueqiu_users/schedules/job_runs/admins/stock_indicator） |
| `repositories/` | `posts/summaries/sectors/groups` 异步读；`sync_data.py` 同步读写(旧 db.py 的忠实移植，供选股/worker)；`jobs.py`(job_runs)；`admins.py` |
| `services/` | `indicators`(纯指标) / `screening`(选股，含预计算快路径) / `matching`(提及/板块/大V看多判定) / `views`(K线/基本面) / `screen_api`(选股编排) / `overview` / `summarizer`(LLM，含总结+菲比问答) / `summaries_build`(分层归并) / `ingest`(快照/财务/板块同步) / `indicator_precompute`(预计算) / `adjust`(K线前复权) / `external/{sina,eastmoney}` |
| `api/routers/public/` | 匿名只读：users/overview/posts/summary*/screen*/stock*/groups(读)/health |
| `api/routers/admin/` | 管理员(JWT 守卫)：auth(登录) / jobs(触发+状态) / config(schedule+分组写) |
| `workers/` | `celery_app` / `queues`(QUEUE_DEFAULT/BROWSER/LLM) / `runner`(job_run 上下文) / `tasks/{stock,browser,summarize,beat}` |
| `scrapers/` | `xueqiu`(抓取) / `kline`(回补) —— playwright 延迟导入，仅宿主 browser worker 执行 |
| `scripts/` | `migrate_sqlite_to_pg` / `verify_migration` / `parity_check` / `create_admin` / `backup.sh` / `adjust_existing_kline`(一次性历史K线前复权迁移) |

## 关键设计决策（改动前必读）

- **异步/同步分界**：轻量读走异步会话；选股/K线是逐字移植的同步逻辑，跑 threadpool + 同步会话，别在事件循环里直接调同步会话。
- **忠实移植 + 对拍**：`sync_data.py`/`services/*` 是旧 `stock.py`/`db.py` 的移植，返回 dict 键与旧库一致；读接口刻意返回原生 dict（不套 Pydantic）以与旧 Flask 逐字节对齐。改选股/指标逻辑后务必保证预计算快路径与现算结果一致。
- **缓存失效**：数据同步任务末尾 `cache.bump_dataver_sync()`（一次 INCR），读接口 key 内嵌 dataver。
- **预计算**：`stock_indicator` 表由 `recompute_indicators` 任务在快照/回补后重算；选股优先读它（`_fresh_indicators()`），表不新鲜则回退现算。别让选股请求再触发全量历史循环。
- **浏览器任务隔离**：`scraper.py`/`kline.py` 不进 API 镜像；抓取/回补进 `QUEUE_BROWSER`，宿主 worker 消费。
- **K线前复权**：新浪K线是不复权价，`kline.py` 回补时用 `sina.fetch_qfq_factors` + `adjust.compute_qfq` 转前复权再落库；`save_history_bars` 写入语义是整行覆盖 OHLC（不是只补空），因为复权价会随未来除权事件变化。改这块务必保证预计算指标表联动重算。
- **跨路由存活的前端单例**：Live2D 挂载状态(`live2d.ts`)、菲比上下文(`pageContext.ts`)、选股页状态(`screenerState.ts`) 都用模块级单例（不进 React 树），因为要跨路由跳转存活；改动时手动同步 `useEffect`，别指望 Context/Provider 语义。

## 本机运行（docker compose，7 服务）

`postgres(5433) · pgbouncer(6432) · redis(6380) · api(8088) · worker · beat · frontend(8090)`
—— **端口是 remap 过的**（本机另有一套微服务栈占用 5432/6379/8000）。浏览器访问 http://localhost:8090。

```bash
cd backend
docker compose up -d
# 首次：alembic upgrade head → python -m scripts.migrate_sqlite_to_pg → verify_migration
# 宿主浏览器 worker：pip install -r requirements-host.txt；celery -A app.workers.celery_app worker -Q browser --pool=solo
```

## 踩过的坑（避免重复）

- **Windows GBK 控制台**：打印 emoji/中文 `UnicodeEncodeError` → 脚本统一 `sys.stdout.reconfigure(encoding="utf-8")`；alembic.ini 保持 ASCII。
- **curl -d 中文 JSON body 会损坏** → 测试用 Python `requests.post(json=...)`，不要 inline curl -d。
- **跨库排序**：中文名在 PG/SQLite collation 下顺序不同（内容一致），列表按需显式 ORDER BY。
- **PgBouncer(edoburu)**：容器内监听 5432（映射 6432:5432）；`AUTH_TYPE=scram-sha-256` 会丢客户端连接，用 `plain`。
- **slowapi**：`@limiter.limit` + headers 需端点声明 `response` 参数 → 用 `headers_enabled=False`。
- **docker.io 拉基础镜像偶发超时** → 重试即可。
- **外部数据源**：新浪 push2 host 被墙（改用 vip.stock/quotes.sina）；新浪板块/新闻接口 GBK 编码需 `decode('gbk')`；东财财务带 Referer 头稳定。批量全市场/全板块循环必须 per-item try/except。
- **中转站视觉模型**：直接传远程图URL会超时 → 本机下载转 base64 data URL 再传。
- **oh-my-live2d 纹理泄漏**：切换模型只摘舞台不释放 WebGL 纹理，连续切换约5次后必定失败 → 切换前手动调用旧模型 `.destroy()`；React StrictMode 下 effect 双调用会挂载两份模型 → 用模块级单例加载，不放进组件 effect 里重复初始化。
- **echarts 触屏手势**：内置 tooltip 自动触发和 pinch 缩放（固定10%步长）体验差 → 关闭自动触发，手动 `dispatchAction` + 长按阈值判断；pinch 改自算真实位移幅度。

## 数据源与限制（不变的业务事实）

- 雪球帖子：Playwright + 真实 Edge，登录态存 `data/edge_profile`（宿主，不入库不入镜像）。
- A股快照：新浪 `Market_Center.getHQNodeData`；历史K线：`quotes.sina.cn`（纯 requests 约250只后 456 永久拒绝，故用真实浏览器页面内 fetch）；财务：东财 `datacenter-web`；板块：新浪 `newFLJK`（GBK）+ getHQNodeData 取成分股。
- 选股预设策略：ma_cross/ma_cross2/golden_cross（均线/MACD/KDJ 金叉，依赖历史K线回补）、fund_ok（财务，依赖财报同步）。

## 文档

- `backend/README.md` —— 运行手册 + 各阶段实现说明
- `doc/服务化重构技术方案与Phase1交付报告.md` —— 方案设计
- `doc/服务化重构分阶段结项总结.md` —— 五阶段结项总结
- `doc/Phase6产品化与体验优化交付报告.md` —— 结项后：K线前复权、AI总结/选股联动、Live2D助手「菲比」、移动端与暗色模式、K线图表交互重做（**当前未提交，未容器化验证**）
