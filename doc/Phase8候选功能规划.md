# Phase 8 候选功能规划（写给下次会话）

| 项 | 内容 |
|---|---|
| 文档类型 | 规划文档（未开工，Phase 7 收尾时整理） |
| 整理时间 | 2026-07-11 |
| 前置状态 | Phase 7 全部 12 项已提交（分支领先 origin 12 个提交，未 push）；第 7–12 项**待部署**：需 `docker compose up -d --build` + `alembic upgrade head` + 宿主端重启 browser worker |
| 用法 | 下次会话按优先级挑选，逐项确认后再开工；每项已写清动机/数据来源/改动点，不必重新调研 |

---

## 0. 开工前必做（Phase 7 收尾，不是新功能）

1. **部署第 7–12 项**：`docker compose up -d --build`（api/worker/beat/frontend 四个都要重建）→ `alembic upgrade head`（迁移 0004）→ 宿主端重启 browser 队列 worker（加载新任务 `browser.sync_xueqiu_sectors`）。
2. **雪球板块全量跑一次**：管理后台点"雪球板块同步（宿主队列）"，观察 134 个行业的实际耗时与失败率。本地只验证过 2 个行业。如果失败率高，考虑给任务加"失败行业单独重试"的断点续跑（记录已成功行业名单，重跑时跳过）。
3. **新浪热门概念全量同步**：管理后台触发"板块名录同步"+"板块成分股全量同步"，验证 700+ 概念及成分股落库；注意 `replace_concept_catalog` 先删后插，低峰期触发。

---

## 1. 板块行情聚合页 ⭐ 最推荐先做（已实现，待验证/部署）

**动机**：Phase 7 把板块数据补全了（新浪行业 + 700+热门概念 + 雪球134申万行业），但板块目前只是选股表格里的"标签"。做一个板块涨跌榜，让三来源数据立刻产生用户可见的价值。

**为什么便宜**：不需要任何新数据源，纯库内聚合——`stock_sector`（成分关系）× `stock_daily` 最新交易日快照（`change_pct` 现成）。

**实现要点**：
- 后端：`services/` 新增板块聚合（按 `sector` 分组算平均涨幅/上涨家数/下跌家数/总市值加权涨幅，任选口径），走同步引擎 + `run_in_threadpool`（模式同 `screen_api`），读接口套 dataver 缓存。
- 路由：`api/routers/public/` 新增 `GET /api/sectors/rank`（列表）+ 复用已有的板块成分股查询做详情。
- 前端：新页面或并入概览页；点板块名进成分股列表（复用 Screener 的表格列定义，含涨跌幅/大V看好）。
- 注意：雪球行业与新浪行业成分股有重叠（同一只股票属于多个来源的板块），榜单按 `board_code` 前缀或 `kind` 分 tab（行业/概念）展示更干净。

**工作量**：后端 1 个聚合函数 + 1 个路由，前端 1 个页面。小。

**实现记录**（本次会话完成，未部署验证）：
- 后端：`repositories/sync_data.py::get_sector_rank`（一条 SQL，`stock_sector` join `sector_catalog` join 最新 `stock_daily`，`GROUP BY sector` 算 member_count/up_count/down_count/avg_change_pct/市值加权涨幅）；`services/sector_rank.py::get_rank` 薄封装（同 `screen_api` 的 `(payload, status)` 模式）；路由 `api/routers/public/sectors.py::GET /api/sectors/rank`，已注册进 `main.py` 路由元组，复用 `cache_ttl_sectors`（未新增专用 TTL）。
- 前端：新页面 `pages/SectorRank.tsx`（路由 `/sectors`，导航栏新增"板块行情"），按 `kind` 用 Segmented 分「行业/概念」两个视图（未按 board_code 前缀再细分来源，行业视图里雪球 xq_/新浪 hangye_ 是混在一起排的——如果后续发现有必要按来源区分可以再加一层 Segmented）；点板块名不是进独立详情页，而是把 `screenerState.sectorNames` 设成该板块 + 带 `autoRun` state 跳转到 `/screener`，复用 Screener 现成的表格列（含涨跌幅/大V看好），省了重新做一套成分股表格。
- `Screener.tsx` 相应加了个 `useEffect` 读 `location.state.autoRun`，进页面自动跑一次筛选并清掉 state（避免用户手动刷新时重复触发）。
- **已验证**：容器已重建（`docker compose up -d --build`），`GET /api/sectors/rank` 用真实数据 curl 验证过，返回结果符合预期（如"激光概念"板块 36 只成分股、up_count 21/down_count 14、avg_change_pct/mv_weighted_change_pct 均在合理区间）；前端 `/sectors` 路由与 nginx `/api` 反代均返回 200。尚未做人工浏览器点击走查。

## 2. 看多热度榜（概览页）（已实现，待部署验证）

**实现记录**：
- 后端：`services/overview.py::get_bullish_heat(days=7, limit=20)`（同步函数，调 `matching.get_bullish_users_map` 按大V数量倒排取前20，用 `db.get_latest_rows()` 补代码/现价/涨跌幅，行情表里找不到名称的丢弃）；路由 `api/routers/public/overview.py` 用 `run_in_threadpool` 调用后合并进 `/api/overview` 响应的 `bullish_heat` 字段，不新增端点/缓存key——沿用现有 `cache_ttl_overview`（300s）+ dataver（`summarize` 任务末尾已 `invalidate_cache=True`，热度榜数据只在总结重新生成后变化，语义对得上）。
- 前端：`types.ts` 加 `BullishHeatItem` + `Overview.bullish_heat`；`Dashboard.tsx` 新增"看多热度榜（近7天）"卡片，排名+标的名（链到个股详情页）+ 现价/涨跌幅 + 看多大V数 + 大V昵称列表。
- **未验证**：容器未重建，`bullish_heat` 字段没有拿真实数据核对过。

**动机**：`matching.get_bullish_users_map()` 已经算出"标的名称→看多的大V列表"，目前只喂给选股表格。反过来聚合就是"最近 7 天被最多大V看多的标的 Top N"，放概览页当核心入口。

**实现要点**：
- 后端：`services/overview.py` 加一段——调 `get_bullish_users_map(days=7)`，按大V数量排序取 Top 20，用 `db.get_latest_rows()` 补上代码/现价/涨跌幅（注意总结里的名称可能匹配不到行情表，漏配的丢弃）。
- 前端：概览页加一张卡片，标的名链到个股详情页。
- 该函数每次全量解析近 7 天日总结，放读接口里要套 dataver 缓存（数据只在总结生成后变化，dataver 语义正好）。

**工作量**：很小，半天级。

## 3. 大V观点时间线（K线叠加喊话点位）

**动机**：`bullish_users` 只有"现在谁看多"。历史观点轨迹（哪天开始提及、方向变化）+ K线上标记"大V提及日"，能直观看到"喊话之后走势如何"。

**实现要点**：
- 数据已有：`summaries` 表按 `period_key`（日期）存每天的结构化总结，`parse_bullish_names` 可逐日解析出方向。个股详情页已有 `get_stock_mentions`（帖子原文提及），这个是"总结判定看多"维度，判据更严谨。
- 后端：新函数——给定股票名称，扫某时间范围内全部日总结，返回 `[{date, user_name, stance}]`。逐日解析全部大V总结开销不小，务必套缓存（dataver）。
- 前端：个股详情页 K 线图用 echarts `markPoint` 在对应交易日上标记，点击弹出"当天谁看多"。
- 风险：按名称匹配（总结里没有稳定代码列），简称/别名会漏。可接受，与 `filter_bullish` 同一已知限制。

**工作量**：中。后端解析 + 缓存设计 + 前端 markPoint 交互。

## 4. 登录态健康检查

**动机**：抓帖子/K线回补/雪球板块三个宿主任务共享一份 `data/edge_profile` 登录态，失效要等任务失败才发现。

**实现要点**：
- 宿主 browser 队列加轻量任务：开页面访问雪球个人主页（或调一个需登录的接口），判断是否跳登录页，结果写 `job_runs`。
- 管理后台加状态卡片：最近一次检查时间 + 有效/失效，失效时红色醒目提示（`login()` 函数已就位，提示用户宿主端手动重新登录）。
- 可挂 beat 定时（如每天早上 8:00），但注意 browser 队列只有宿主 worker 消费，宿主没开机时任务会堆积——beat 派发前查队列深度或设 expires。

**工作量**：小。

## 5. job_runs 运行历史页

**动机**：管理后台每类任务只能看最新一次状态，排查"昨晚定时任务为什么没跑"没有抓手。

**实现要点**：
- `repositories/jobs.py` 加分页查询（按 kind 筛选，倒序）；`api/routers/admin/jobs.py` 加 `GET /api/jobs/history`。
- 前端 Admin 页加一个 Table（kind/来源/状态/开始/耗时/错误信息），失败行可展开看 error。
- 表数据已齐全（`job_runs` 从 Phase 3 就在记录），纯读接口 + UI。

**工作量**：小。

## 6. 选股结果导出 CSV

**动机**：表格加了板块/概念/大V列后信息密度够高，导出诉求自然出现。

**实现要点**：纯前端做——`rows` 状态已在 `screenerState` 单例里，拼 CSV 字符串 + Blob 下载即可，不需要后端。注意 Excel 打开 UTF-8 CSV 乱码问题，加 BOM 头 `﻿`。数组字段（sectors/bullish_users）用 `、` 连接。

**工作量**：极小，1 小时级。

## 7. PWA 桌面通知（往后放）

**动机**：周总结生成完成或大V发新帖时推送。
**为什么往后放**：Web Push 需要 VAPID 密钥 + 推送订阅存储 + 后端推送服务，且 iOS 支持有限；现有 sw.js 是"可安装"级别的极简实现，升级成本中等。等前面的都做完再议。

---

## 建议的开工顺序

**第一批（一次会话可完成）**：0（部署+全量验证）→ 1（板块聚合页）→ 2（热度榜）。0 是收尾义务，1/2 都是纯库内聚合，风险低、用户可见价值高。

**第二批**：5（job_runs 历史）→ 4（登录态检查）→ 6（CSV导出）。全是小件，凑一次会话。

**第三批**：3（观点时间线，需要好好设计缓存与交互）→ 7（通知，需要评估）。

## 涉及的既有约定（改动时别违反）

- 重计算走同步引擎 + `run_in_threadpool`，别在事件循环里调同步会话（CLAUDE.md"异步/同步分界"）。
- 读接口套 dataver 缓存；数据写入任务末尾 `bump_dataver_sync()`。
- browser 队列任务只能宿主跑，代码里 playwright 保持延迟导入。
- 前端跨路由状态用模块级单例，别引入 Context/Provider。
- 改动后不主动跑 build/重启容器，等用户明确要求（用户偏好）。
