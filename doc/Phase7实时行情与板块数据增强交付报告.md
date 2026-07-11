# 雪球大V看板 & A股选股系统 —— Phase 7 实时行情与板块数据增强交付报告

| 项 | 内容 |
|---|---|
| 文档类型 | 阶段交付报告（Phase 6 产品化打磨之后的功能增强） |
| 版本 | v2.0 |
| 周期 | 2026-07-11（Phase 6 提交之后至本次同步） |
| 状态 | 全部 12 项已提交；前 7 项已容器化部署验证，后 5 项待部署（见第 6 节） |
| 范围 | 秒级个股行情、全市场10分钟自动同步、周总结定时、按需重生日总结、新闻深链接提示、PWA支持、定时任务开关、雪球板块数据源、新浪热门概念、选股结果板块/大V看好列、大V多选筛选、Live2D收起召回 |
| 关联代码 | `backend/app/{services/external/sina,services/{matching,screen_api,ingest},api/routers/public/stocks,workers/tasks/*,scrapers/xueqiu,repositories/sync_data}.py`、`frontend/src/{api,pages,public}/*`、`frontend/src/live2d.ts` |

---

## 1. 背景

Phase 6 完成产品化打磨后，本轮迭代围绕三条主线展开：**"数据要更实时"**（个股详情页秒级刷新、全市场行情不再依赖手动点触发）、**"数据要更全"**（板块分类补上新浪缺失的半导体/软件开发等新兴行业，概念板块从多年未更新的旧分类切换到新浪现行维护的"热门概念"）、**"数据要用起来"**（板块/概念/大V观点直接附加到选股结果表格，形成"策略信号 × 板块题材 × 大V观点"的交叉视角）。同时补齐了一些运营侧的可控性（定时任务开关）和触达便利性（PWA 添加到主屏幕）。

---

## 2. 变更概览

| # | 主题 | 触发原因 | 影响范围 | 状态 |
|---|---|---|---|---|
| 1 | 个股秒级行情 | K线走300s缓存，无法反映盘中价格跳动 | 新增 `/api/stock/quote` + 前端1s轮询 | 已部署 |
| 2 | 全市场10分钟自动同步 | 行情同步此前只能手动触发 | 新增交易时段感知的 beat 任务 | 已部署 |
| 3 | 周三/周日周总结定时 | 周总结此前只能手动触发 | crontab + 门槛任务 | 已部署 |
| 4 | 抓帖子后按需重生日总结 | 当天已生成过总结后，新帖子不会触发更新 | `crawl_all` 返回值 + 强制 regen | 已部署 |
| 5 | 新闻深链接提示 | 部分个股新闻链接在手机浏览器打开后变404 | StockDetail 前端提示 | 已部署 |
| 6 | PWA 添加到主屏幕 | 朋友访问需每次手动找网址 | manifest/icons/sw.js | 已部署 |
| 7 | 定时任务开关 | 10分钟同步/周总结缺少开关，不像"定时采集"能控制 | schedules 表迁移0004 + 管理后台UI | 已提交，待部署 |
| 8 | 雪球板块数据源 | 新浪板块分类缺半导体/软件开发等新兴行业 | 新增宿主队列任务 `sync_xueqiu_sectors` | 已提交，待部署 |
| 9 | 新浪热门概念板块 | 旧 `gn_` 概念分类多年未更新，缺AI应用/具身智能等 | 概念名录切换到 getHQNodes"热门概念"子树（700+个） | 已提交，待部署 |
| 10 | 选股结果板块/大V看好列 | 选出的股票缺少题材与大V观点上下文，需逐只点进详情页看 | `attach_sectors`/`attach_bullish_users` + 前端3列 | 已提交，待部署 |
| 11 | 大V筛选多选 | "只看大V提及"只能选一位或全部，无法圈定关注的几位 | `user_id` 单选升级为 `user_ids` 多选（后端兼容旧字段） | 已提交，待部署 |
| 12 | Live2D 菲比收起/召回 | 舞台常驻遮挡内容，无法临时收起 | `live2d.ts` 菜单项 + statusBar 召回 | 已提交，待部署 |

---

## 3. 详细变更

### 3.1 个股秒级实时行情

- `services/external/sina.py` 新增 `fetch_realtime_quote(code)`：走 `hq.sinajs.cn` 单股查询接口（几十毫秒级响应，纯 requests），返回最新价/开盘/最高/最低/成交量/交易日期。
- `api/routers/public/stocks.py` 新增 `GET /api/stock/quote`：1秒短TTL缓存兜底——无论多少用户同时看同一只股票，对上游新浪的请求频率封顶在 1次/秒/股票；不走 dataver 版本失效（quote 本身就是实时的，不需要数据同步后失效这层语义）。
- 前端 `useQuote`（1000ms 轮询）只合并展示"今天这根K线"的 close/high/low/volume，MA/MACD/KDJ 等技术指标仍是日级值不随之重算——这些指标本质是收盘价的日线计算，盘中用最新价重算意义不大，还会造成"信号一会儿出现一会儿消失"的抖动。`quote.trade_date` 与K线最后一天不一致时（今天还没做过快照同步）不合并，不在前端凑一根后端没算过指标的假K线。

### 3.2 全市场行情10分钟自动同步

- `workers/tasks/stock.py` 新增 `task_auto_sync_tick`：固定600秒周期（beat_schedule），只在A股交易时段（9:15-11:30、13:00-15:05，工作日）内派发；若上一轮 `stock_sync` 或其触发的 `recompute_indicators`（全表重算）还没跑完则跳过本轮，避免行情接口偶发变慢时任务在队列里堆积。

### 3.3 周三/周日20:00周总结定时

- `workers/celery_app.py` 新增 crontab(`hour=20, minute=0, day_of_week="0,3"`)，触发门槛任务 `summarize.weekly_tick`（`workers/tasks/summarize.py`），检查开关后派发现成的 `summarize.run(ptype="weekly")`。
- 两次触发生成的是**同一份**周总结（`period_key` 相同，如 `2026-W28`）：周三先出"半周版"（周一到周三的帖子），周日用同一 key 覆盖生成"完整版"（周一到周日全量），不是两份独立总结，也不会跨到下一周。

### 3.4 抓帖子后按需重生当日总结

- 之前的隐患：`task_crawl` 抓完后无差别给所有大V派发总结任务，但内部走 `ensure_daily`（命中缓存不重算）——当天已经生成过一次总结的大V，即使后续定时抓取抓到了新帖子，也不会重新生成，页面上看不出变化。
- `scrapers/xueqiu.py::crawl_all` 改为返回 `{user_id: (user_name, 新增条数)}`，只包含本次真的抓到新帖子的大V；`task_crawl` 只给这些大V派发 `task_summarize_daily_one(regen=True)` 强制重新生成，没有新帖子的大V不再无脑重跑一遍 LLM。

### 3.5 个股新闻深链接提示

- 新浪个股新闻里约1/3的链接是"新浪看点"域名（`cj.sina.cn`/`t.cj.sina.cn`），是给其App用的深链接跳转页，部分手机系统浏览器（尤其国产定制ROM）打不开对应App时会短暂显示内容后跳转到404。链接本身来自新浪，无法在前端改写，`StockDetail.tsx` 按域名判断后加一个提示图标告知用户。

### 3.6 PWA 支持（添加到主屏幕）

- 新增 `public/manifest.json` + `public/icons/`（K线主题图标，512/192/maskable/apple-touch/favicon 全尺寸）+ `public/sw.js`（极简 service worker，只用于让浏览器判定"可安装"，`/api/` 请求原样直通网络不缓存）。
- `index.html` 接入 manifest/图标；iOS Safari 不认 manifest.json，单独加 `apple-mobile-web-app-*` meta 标签。
- 鸿蒙（含 HarmonyOS NEXT）默认浏览器内核是基于 Chromium/Blink 的 ArkWeb/NWeb，走标准 manifest 协议，这份配置无需额外适配即可覆盖。

### 3.7 定时任务开关

- 数据库迁移 `0004_schedule_toggles.py`：`schedules` 表新增 `stock_auto_sync_enabled`、`weekly_summary_enabled` 两个字段，默认 `true`（不影响已上线的行为）。
- Celery beat 的周期配置是进程启动时的静态字典，没有运行时暂停/恢复的机制；开关统一做成"任务函数第一件事读 `schedules` 表对应字段，不满足就 `return`"（范例见既有的 `tasks/beat.py::scheduler_tick`）。周总结的开关不能直接加在 `summarize.run` 里（它也被管理后台手动触发复用），改成单独的门槛任务 `summarize.weekly_tick` 读开关后再派发，`stock.auto_sync_tick` 直接在函数体内读开关。
- 管理后台"定时任务"面板（原"定时采集"）新增两个 Switch：**全市场行情10分钟同步**、**周三/周日周总结**。

### 3.8 雪球板块数据源

**问题**：新浪板块行业分类比较老旧，没有"半导体""软件开发"这类近年热点分类。调研确认雪球有134个申万行业分类（`stock.xueqiu.com/v5/stock/screener/industries.json`），包含半导体（S2701）、软件开发（S7104）、计算机设备（S7101）、IT服务（S7103）等新分类。

**技术约束**：
- 雪球板块名单接口拒绝匿名请求（纯 requests 直接 400），必须在已登录的浏览器页面内用 `page.evaluate` fetch（带 cookie）。
- 成分股页面是纯前端渲染，没有独立JSON接口，只能读DOM表格：点击"90"（每页条数）+ 循环点击"下一页"直到按钮 `disabled`。本地验证：化学制品行业180+只成分股，分2页（90+57，含一个非90整数的尾页）抓取干净，"下一页"按钮在最后一页正确变为 disabled，是可靠的停止条件。
- 雪球代码带交易所前缀（`SH600745`），需转成纯6位数字（`_xq_code_to_plain`）才能与项目统一的 `stock_daily.code` 格式对齐。

**实现**：
- `scrapers/xueqiu.py` 新增 `fetch_industries`（134行业名录）、`scrape_industry_members`（单行业成分股翻页抓取）、`sync_xueqiu_sectors`（整体编排，per-item 容错，单个行业失败跳过不影响其余）。
- `workers/tasks/browser.py` 新增 `task_sync_xueqiu_sectors`（`QUEUE_BROWSER` 宿主队列专用）。
- `repositories/sync_data.py` 新增 `save_xueqiu_sectors`：写入前对 `sector_catalog.name` 做唯一性检查——雪球与新浪有5个行业重名（教育/体育/渔业/林业/综合），撞名时**保留已有的那条，跳过雪球新来源的同名行**，成分股也不写，避免覆盖已有同名板块的成分股关系。本地验证：半导体（51只）、软件开发（94只）正确落库为 `xq_S2701`/`xq_S7104`；教育（撞名）正确跳过，原新浪教育板块10条成分股关系完全不受影响。
- `services/matching.py::get_sector_members` 新增短路：`xq_` 前缀的板块读不到缓存时直接返回空，不去现拉（雪球没有可容器化的现算路径，只能靠后台任务批量预抓）。
- `api/routers/admin/jobs.py` 新增 `POST /api/stock/sync-xueqiu-sectors`；前端 `Admin.tsx` 新增"雪球板块同步（宿主队列）"按钮。

### 3.9 新浪"热门概念"板块（概念维度补全）

**问题**：雪球没有"概念板块"维度（3.8 只补了行业）；而新浪旧的 `newFLJK class` 概念分类（`gn_` 前缀，175个）多年未更新，缺"AI应用""具身智能"这类新概念。调研发现新浪 `getHQNodes` 节点树接口的"A股/热门概念"子树（`chgn_` 前缀，700+个）是新浪现在实际维护的概念分类，且成分股走同一套 `getHQNodeData` 分页接口，`fetch_board_members` 无需改动即可复用。

**实现**：
- `services/external/sina.py` 新增 `fetch_hot_concepts()`：解析 getHQNodes 节点树，取"A股→热门概念"子树。
- `repositories/sync_data.py` 新增 `replace_concept_catalog`：概念名录**整体替换**旧 `gn_` 数据（先删全部旧概念及其成分股关系，再整批插入）。用替换而非追加，是为了绕开 `save_sector_catalog` 的撞名跳过逻辑——新旧概念经常同名但覆盖范围不同，追加会导致新数据被当撞名吞掉。概念名与行业名撞车时（如"电网设备"同时是雪球行业名）跳过概念，保留行业。
- `services/ingest.py::sync_sector_catalog` 拆成两条路径：行业走追加式 `save_sector_catalog`（与雪球共享撞名逻辑），概念走 `replace_concept_catalog`。

### 3.10 选股结果附加板块/概念/大V看好列

**动机**：选股结果只有行情/财务数字，选出来的股票"是什么题材、有没有大V在关注"要逐只点进详情页看。本项把三类上下文直接附加到结果表格，形成"策略信号 × 板块题材 × 大V观点"交叉视角。

- `matching.attach_sectors`：给每行加 `sectors`（所属行业）/`concepts`（概念题材）字段，按 `sector_catalog.kind` 拆开；再各配 `bullish_sectors`/`bullish_concepts` 子集，标出哪些板块/概念名下有股票最近被大V看多（前端对应标签描红框）。底层 `get_sectors_by_codes` 批量一次查完，不逐行查询。
- `matching.attach_bullish_users`：给每行加 `bullish_users`（哪些大V最近看多这只标的）。`get_bullish_users_map` 一次查完全部大V近7天日总结，反向建"标的名称→大V"索引，每行 O(1) 查表。
- `derive_bullish_sectors` 判据从"板块名在帖子原文出现过"改为严谨口径：读日总结结构化"看多"标的反推其所属板块——与"大V看好"列、`filter_bullish` 同一套判据。
- 前端 `Screener.tsx` 新增"所属板块""概念题材"（`CollapsibleTags`，超6个折叠为"+N"）与"大V看好"三列。

### 3.11 大V筛选支持多选

- "只看大V提及"/"大V看多的板块"的大V筛选从单选 `user_id` 升级为多选 `user_ids`（空数组 = 全部大V）。
- 后端 `screen_api._parse_user_ids` 同时兼容旧的 `user_id` 字符串字段，老客户端请求不受影响；`matching` 层 `match_mentions`/`filter_bullish`/`derive_bullish_sectors` 签名统一改为 `user_ids: list[str]`。

### 3.12 Live2D 菲比收起/召回

- 菲比舞台常驻右下角，遮挡表格内容且无法临时收起。难点：操作菜单挂在舞台元素内部，`stageSlideOut` 后菜单跟着滑出屏幕，点不到"召回"。
- 借用 oh-my-live2d 自带的 statusBar（"休息条"，挂在独立于舞台的元素上）作召回入口：菜单新增"收起菲比"项，点击后舞台滑出 + 休息条弹出"点我召回"，点休息条 `stageSlideIn` 召回并关闭休息条。

---

## 4. 关键设计取舍

1. **秒级行情与日级指标分离缓存**：`quote` 接口用独立的1秒短TTL key，不复用 dataver 版本失效体系，因为它的"新鲜度"语义与其他缓存完全不同（永远要最新，不是等数据同步后才失效）。
2. **三个来源共用同一套板块表**：不为雪球/热门概念单独建表，复用 `sector_catalog`/`stock_sector`，靠 `board_code` 前缀（`xq_` / `chgn_` / 新浪原有的 `hangye_`）区分来源；下游读取路径（选股筛选、个股详情页板块标签、attach_sectors）完全不用改，是"读接口对数据源无感"这个既有设计的自然延伸。
3. **行业追加、概念替换，两种落库语义**：行业分类稳定且多来源互补，用追加+撞名跳过；概念分类整体换代（旧 `gn_` → 新 `chgn_`），用整体替换避免新旧同名互相干扰。`name` 全局唯一约束是两种语义共同的裁判。
4. **雪球板块同步不做定时，只做手动按钮**：板块归属不会经常变，且任务耗时长（134个行业逐个翻页）；同时刻意不引入并行加速（登录态是单一份、雪球有反爬风控），保持跟抓帖子/K线回补一样的"宿主机常驻+偶尔人工过一下滑块验证"模式。
5. **拒绝接入验证码打码平台**：雪球滑块验证是反爬机制，故意需要人类交互；打码平台本质是自动化绕过反爬，封号风险显著高于现状，评估后决定不引入。
6. **"看好"判据统一走结构化总结**：板块看好、股票看好、大V归属三处全部基于日总结的"提到的标的"表格方向列解析（`parse_bullish_names`），不做原文关键词匹配——口径一致，且不会把"提到但看空"误标成看好。

---

## 5. 风险与遗留

| 项 | 说明 | 建议 |
|---|---|---|
| 雪球板块全量未跑 | 代码已提交、本地验证过2个行业，134个行业全量还没跑过 | 部署后在宿主 browser worker 上手动触发一次，观察实际耗时与失败率 |
| 概念板块整体替换的窗口期 | `replace_concept_catalog` 先删后插不在同一语句，同步任务执行的数秒内板块查询可能读到空概念 | 任务在低峰手动触发即可接受；如需严格原子可改为同事务内 swap |
| 雪球登录态单点依赖 | 抓取/回补/板块同步都依赖同一份 `data/edge_profile` 登录态，过期或封号会同时影响三个功能 | 定期人工验证登录态有效性；`login()` 函数已就位，过期后手动重新登录即可 |
| 板块名重名跳过策略是单向的 | 撞名永远保留先入库的、跳过新来源；如果未来想让新来源覆盖旧数据 | 需要手动调整跳过逻辑或先清理冲突的旧数据 |
| bullish_users 按名称匹配 | AI总结里没有稳定的代码列，按标的名称匹配可能漏掉简称/别名写法 | 现状可接受；如需提升召回率可在总结 prompt 里要求带代码 |

---

## 6. 验证情况

| 项 | 验证方式 | 结果 |
|---|---|---|
| 秒级行情接口 | 容器内直接调用 + 经 nginx 反代请求 | 返回正常，1s缓存自然过期后能取到最新价 |
| 全市场10分钟同步 | beat_schedule 注册检查 + 交易时段判断单测（周末/午休/开收盘边界） | 通过 |
| 周总结定时 | crontab 表达式解析检查（`0 20 * * 0,3`） | 通过 |
| 抓帖子按需重生 | 代码审查 + py_compile | 通过（未跑真实抓取场景，依赖宿主 worker） |
| 新闻深链接提示 / PWA | `npm run build` + 容器内验证 manifest/sw.js/图标可访问 | 通过 |
| 定时任务开关 | 迁移已在数据库跑通，写入/读取往返验证，前端资源确认包含开关文案 | 通过 |
| 雪球板块同步 | 本地脚本验证：半导体51只、软件开发94只成分股正确落库；教育撞名正确跳过，原有数据不受影响 | 小范围通过，**134行业全量未跑** |
| 热门概念 | 本地调用 `fetch_hot_concepts` 确认返回700+概念；`replace_concept_catalog` 旧删新插往返验证 | 通过 |
| 选股附加列 / 大V多选 | 后端 `screen` 接口带 `user_ids` 请求对拍 + 前端 `npm run build` | 通过 |
| 菲比收起/召回 | 浏览器手动操作：收起→休息条出现→点击召回 | 通过 |

**部署提醒**：本轮第 7–12 项提交后尚未重新 `docker compose up -d --build`；其中迁移 0004 需要 `alembic upgrade head`，雪球板块任务需要宿主端重启 browser 队列 worker 才能加载新任务注册。

---

## 7. 相关文档

- 架构与五阶段结项：`doc/服务化重构分阶段结项总结.md`
- 方案设计与 Phase 1 详情：`doc/服务化重构技术方案与Phase1交付报告.md`
- Phase 6 产品化与体验优化：`doc/Phase6产品化与体验优化交付报告.md`
- 运行手册：`backend/README.md`
