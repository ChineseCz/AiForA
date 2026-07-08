# 项目速览（写给下一次会话的 Claude）

单用户本地工具，两条主线：① 雪球大V帖子抓取+AI总结；② A股行情/财务/板块数据 + 选股筛选看板。
无 git 仓库，无测试框架，纯个人使用，改动后靠手动跑 CLI / curl / 浏览器验证。

## 模块职责

| 文件 | 职责 |
|---|---|
| `config.py` | 读 `.env`：中转站API key、雪球用户列表、抓取节流、`HEADLESS`、各路径 |
| `scraper.py` | 雪球帖子抓取，Playwright 驱动**真实 Edge**（复用 `data/edge_profile`，绕雪球阿里云WAF） |
| `summarizer.py` | AI 日/周/月/年总结 + 精华帖提炼，分层归并省token（周月复用日总结，年复用月总结） |
| `db.py` | 唯一的 SQLite 访问层（`data/posts.db`），所有表结构与查询集中在这 |
| `stock.py` | 行情/财务/板块数据抓取 + 选股筛选/技术指标计算，全部逻辑在这，无独立数据源模块 |
| `web.py` | Flask 网页看板，`app.run()` 全局唯一实例；路由清单见下 |
| `main.py` | CLI 入口，`argparse` 子命令，见下表 |
| `templates/index.html` / `static/js/app.js` / `static/css/style.css` | 单页看板前端，原生JS，无框架 |

## 数据源与已知限制

- **雪球帖子**：Playwright + 真实 Edge，登录态存 `data/edge_profile`。`HEADLESS=false`（默认，不易被识别）。
- **A股行情快照/历史K线/财务**：都是直连公开接口，**项目不用 akshare**。
  - 实时快照：新浪财经。
  - 历史K线：`quotes.sina.cn` `CN_MarketDataService.getKLineData`。**该接口对纯requests请求反爬阈值极低**
    （约250只顺序请求后返回456永久拒绝，跟IP绑定，短期不解除）。解法是用 Playwright 驱动真实 Edge
    在页面内同源 `fetch`（`stock.py: backfill_history`），反爬识别的是"是否真实浏览器指纹"而非纯限流——
    实测连续500只0失败，约0.6~0.8秒/只，全量5526只约1小时，会弹出可见浏览器窗口，跑完自动关闭。
  - 财务指标：东方财富 `datacenter-web.eastmoney.com`（带 `Referer` 头，实测稳定）。
  - 板块列表/成分股：**2026-07-07 已从东方财富 `push2.eastmoney.com` 换成新浪**——`push2` 在本机网络下
    100%必挂（`RemoteDisconnected`，不是偶发），同一台机器上 `datacenter-web.eastmoney.com` 却完全正常，
    说明是`push2`这个host被挡，不是东财整体的问题。行情快照那块（第23行）其实早就因为同样原因绕开了
    `push2` 换用新浪，板块是当时唯一没跟上的。现方案：分类列表用
    `http://vip.stock.finance.sina.com.cn/q/view/newFLJK.php?param=class`（概念，返回体是GBK编码的
    `var S_Finance_bankuai_class = {...}`，需要 `r.content.decode('gbk')` 再从文本里正则抠出JSON对象；
    直接 `print()`/在git-bash里看这段解码结果会显示乱码，那是**终端显示问题**，不是解码错了，字符编码
    用`ord()`验证过是对的）/`param=class_dp`（行业）；成分股复用行情快照同一个
    `Market_Center.getHQNodeData` 接口，`node`参数传板块的 `board_code`（如`gn_hwqc`/`hangye_ZA01`），
    分页拿全量。`sector_catalog.board_code` 字段格式因此从东财的`BK0428`变成了新浪的`gn_xxx`/`hangye_xxx`，
    纯字符串id，其它代码都不解析这个字段的格式，无影响。

## 数据库表（db.py）

- `posts` / `summaries` —— 雪球帖子去重入库 + 各周期总结缓存
- `stock_daily` —— 行情快照 + 历史K线合流，`UNIQUE(trade_date, code)`
- `stock_finance` —— 最新一期财务指标（EPS/ROE/净利润同比/营收同比/毛利率）
- `stock_groups` / `stock_group_members` —— 自选股分组
- `sector_catalog` —— 板块名录（行业+概念，`board_code`/`name`/`kind`）
- `stock_sector` —— 板块成分股缓存，7天有效期（`get_sector_members_cached`）

## 帖子配图识别（2026-07-07 已实现+验证过）

之前 `raw_json` 一直硬编码空字符串，等于从未存过任何配图信息，`clean_text` 用 BeautifulSoup
`get_text()` 也会把 `<img>` 标签连带信息一起丢掉——**不是遗漏，是从没做过**。现状：`posts` 表新增
`images`（JSON数组，配图URL列表）/`image_desc`（视觉模型描述缓存）两列，`db.init_db` 里用
`PRAGMA table_info` 探测+`ALTER TABLE ADD COLUMN` 给旧库自动迁移（`CREATE TABLE IF NOT EXISTS`
不会给已存在的表加列）。

抓取端 `scraper.extract_images(status)`：单图帖子直接用雪球原始字段 `pic`；多图帖子
（`is_ss_multi_pic`）该字段只有第一张，其余图在 `image_info_list` 里但只给 `filename`没有完整
URL，用 `pic` 的主机前缀（`xqimg.imedao.com`）拼出来（实测同一帖子内一致）。**统一去掉雪球URL
的 `!thumb.jpg` 尺寸后缀取原图**——同一张图缩略图仅3.5KB、原图104KB，实测拿缩略图给视觉模型描述
只能说"文字模糊看不清"，换原图能准确读出个股名称/涨跌幅数字/指数点位，差距很大。只对**新抓取**的
帖子生效：`crawl_user` 里 `db.post_exists` 已经跳过的旧帖子不会走到这段逻辑，库里历史帖子从未存过
配图URL，没法回填，只能是这次改动之后新抓的帖子才有图。

总结端 `summarizer.ensure_image_desc(post)`：命中 `posts.image_desc` 缓存直接返回，否则调用
`describe_images` 并写回缓存，`_format_posts`（日总结/精华帖共用）里把描述文本拼进"配图内容"塞进
prompt。周/月/年总结走 `reduce_period` 复用的是已经含配图描述的日总结markdown文本，天然不会重复
调用视觉模型，跟既有的"分层归并省token"思路一致，不需要额外处理。

日总结/精华帖的返回值末尾还会拼一段"### 配图"小节（`summarizer._images_appendix`），把原图按
Markdown `![]()` 语法直接嵌进去，供网页端渲染（`web.py _render_md` 用的 `markdown` 库本身就支持
图片语法，不用额外处理）。**这段图片链接是代码直接从 `posts.images` 拼的，不经过LLM**——让LLM在
总结正文里转抄URL有编错/编造的风险，宁可用确定性拼接。`reduce_period`（周/月/年）故意不做这个
拼接，因为它的输入已经是归并过的总结文本而非原始帖子，跟单张图片不再是一一对应关系。

**踩过的坑**：一开始直接把雪球图床URL传给视觉模型（`image_url: {"url": 远程URL}`），中转站报400
`Unable to download content from the provided URL before the timeout`——本机直连这个CDN完全正常
（`requests.get` 秒回200），说明是**中转站服务器自己的出口网络访问雪球CDN不稳定**，跟"push2被墙"
不是一回事（那个是host被墙，这个是中转站那端超时）。**修复**：改成本机先用 `requests` 把图片下载
下来，`base64` 编码成 `data:image/jpeg;base64,...` 的 data URL 再传给视觉模型
（`summarizer._image_to_data_url`），不再依赖中转站自己去拉远程URL。

`config.VISION_MODEL`（默认沿用 `RELAY_MODEL`，可在 `.env` 单独配置）：当前中转站配置的模型本身
就支持视觉输入，已用真实雪球帖子截图验证过（能准确读出图中股票名称和涨跌幅数字）。如果之后换了
不支持视觉的模型做 `RELAY_MODEL`，需要单独配 `VISION_MODEL` 指向一个支持视觉的模型名，否则
`describe_images` 会报错（`ensure_image_desc` 已用 try/except 兜底，失败只是跳过配图描述，不影响
其余总结流程）。

明确排除的范围：视频（`video_info`/`vod_info` 字段存在但没做，雪球帖子偶尔带视频，这轮不处理）。

## 已修复的历史bug：历史K线开盘价大面积NULL

`save_history_bars` 用 `INSERT OR IGNORE`（避免回补的历史行覆盖掉已有的完整快照行），但这导致早期
版本"漏采 open 字段"时写入的旧行，即使后来代码修好了 open 采集，重跑回补也会因为 `(trade_date, code)`
唯一键冲突被直接 `IGNORE` 跳过，新值进不去。现在的修复：`INSERT OR IGNORE` 之后再加一次
`UPDATE stock_daily SET open=? WHERE trade_date=? AND code=? AND open IS NULL`，只补空不动其它字段。
**2026-07-07 状态：已解决。** 代码修复本身早就在（`backfill_history` 按字段名解析、非位置索引，无OHLC
错位问题），问题只是"从未被跑一次回补真正触发过"——当时库里330386行历史行中324860行 open 为 NULL。
跑了 `python main.py stock-backfill --days 365 --delay 0.5`（把历史范围从109个交易日/2026-01-20~07-06
扩展到近365天），结果：**成功 5526 只，失败 0 只**，NULL open 补齐。如果之后又出现大面积 open IS NULL，
说明有新一批股票的采集又漏了字段，按同样思路重跑这条CLI命令即可（`main.py` 的 `--days` 无cap；但
`web.py /api/stock/backfill` 这个API路由把 days 强制clamp到 20~120，只适合日常小范围补，大范围回补
要用CLI，别指望网页按钮）。

## Web路由（web.py，按功能分组）

- 帖子看板：`/` `/api/users` `/api/overview` `/api/posts` `/api/summary*` `/api/crawl*` `/api/schedule`
- 行情/财务同步（各自 running/log/error 状态 + 后台线程，同一套模式）：
  `/api/stock/sync*` `/api/stock/backfill*` `/api/stock/finance_sync*` `/api/stock/sync-sectors*`
  `/api/stock/sync-sector-members*`（板块成分股全量同步，同一套后台线程模式）
- 选股筛选：`/api/screen`（数值条件`build_where` + 提及过滤`match_mentions` + 板块过滤`match_sector`）、
  `/api/screen/fields`、`/api/screen/sectors`、`/api/screen/preset`
- 个股详情：`/stock/<code>`、`/api/stock/kline`、`/api/stock/fundamentals`（财务+所属板块+大V提及）
- 自选分组：`/api/groups*`

## CLI子命令（main.py）

`login` `crawl` `summary {daily,weekly,monthly,yearly}` `highlights` `stats`
`stock-sync`（快照）`stock-backfill --days --delay`（历史K线，默认60天，**无上限**）
`stock-sync-finance`（财报）`stock-sync-sector-members`（板块成分股全量同步，见下方"个股详情页基本面"节）
`serve --host --port`（默认 127.0.0.1:5000）

## 板块筛选功能（"筛选条件"面板新增维度，已实现+验证过）

手动选板块，或选"当前大V看多的板块"（`derive_bullish_sectors`：复用大V最近N天帖子文本，做板块名称
子串匹配 `extract_sectors_from_text`，命中即算"看多"，不做真实情感分析——这是有意的简化，跟已有的
`match_mentions`"提及即命中"哲学一致）。前端 `#sectorEnabled`/`#sectorMode`/`#sectorSelect`/`#sectorDays`
在 `templates/index.html`，逻辑在 `app.js`（grep `sector` 各命中10/23处）。

## 个股详情页"基本面"（2026-07-07 已实现+验证过）

`/stock/<code>` 页面在K线图下方新增了基本面面板：财务指标（`stock_finance`）、所属板块（反查
`stock_sector`）、大V提及（反查 `posts`，判定口径跟 `match_mentions` 一致，只是方向反过来——按股票
代码/名称找帖子而非按帖子找股票，见 `stock.get_stock_mentions`）。数据由新接口 `/api/stock/fundamentals?code=`
一次性打包返回（`stock.get_fundamentals_view`），刻意跟 `/api/stock/kline` 分开，避免K线缩放/hover时
重复计算基本面。**"所属板块"要完整展示，前提是先跑过一次板块成分股全量同步**（`stock-sync-sector-members`
CLI 或网页"数据同步"面板里的"板块成分股全量同步"按钮）——`stock_sector` 平时是懒加载（只有筛选时用到
哪个板块才去拉），全量同步就是主动把 `sector_catalog`（259个板块）全部跑一遍 `get_sector_members`。

## 个股详情页"相关新闻"（2026-07-08 已实现+验证过，此前CLAUDE.md曾写"不做"，已过时）

后来还是做了。数据源新浪财经个股资讯页 `vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php`
（`stock.fetch_stock_news`），跟板块分类接口 `newFLJK.php` 同一路数据源，同样是GBK编码——正文用正则
`_NEWS_ITEM_RE` 从HTML里抠`日期/时间/链接/标题`，翻页按天数过滤（页面本身按时间倒序，翻到整页最旧
一条都早于截止日期就停，不用翻到底）。新接口 `/api/stock/news?code=`（`web.py`），前端
`kline.js: loadStockNews/renderNews` 渲染进 `kline.html` 的 `#fundaNews` 区块，跟"大V提及"一样是
独立面板、单独fetch，不影响K线/基本面主数据。**用真实股票代码`requests.get`+`r.json()`验证过能拿到
78条新闻**，标题在git-bash里 `print()` 直接看是乱码——跟第35行"class_dp解码乱码是终端显示问题"是
同一类坑，用 `ord()` 逐字符验证过实际解码是对的（UTF-8 JSON响应本身没问题）。任何请求失败都吞掉
打日志，返回已拿到的部分，不影响基本面页其余内容（跟"大V看多板块"同样的"辅助信息、失败不阻塞主
流程"原则）。

**踩过的坑**：`sync_all_sector_members` 循环259个板块时，第一版没有 per-item try/except，某个板块
（如"整体上市"）偶发返回非JSON响应（`r.json()` 抛 `Expecting value`），直接中断整个批次，导致后面
~200个板块全部没同步到。**已修复**：改成每个板块单独 try/except，失败就跳过+打日志，最后汇总失败数
（不再让一个板块的偶发失败拖垮全量同步）。这跟第29行"`push2`被墙"是同一个"新浪/东财接口偶发不稳定"
类问题，教训是：任何循环全市场/全板块的批量任务都要 per-item 容错，不能假设外部接口对所有输入都稳定。

## 本机环境注意事项（踩过的坑，避免重复）

- **Windows允许多个进程同时监听同一TCP端口**：`Get-NetTCPConnection -LocalPort X -State Listen` 可能
  同时返回多个 `OwningProcess`。新起的测试服务器能成功bind、打印banner、零报错，但curl请求可能一直
  打在另一个更早启动的旧进程上。开测试服务器前务必确认该端口只有一个PID在监听，且其`CreationDate`
  晚于最新代码改动时间。
- **`python web.py` 直接跑没有 `--port` 参数**（硬编码5000，`run()`无argparse）。要自定义端口用
  `python main.py serve --port XXXX`（main.py的argparse会正确传递）。
- **git-bash/Windows下 `curl -d` 发送含中文的JSON body可能在传输前被破坏**，导致Flask端
  `request.get_json(silent=True)` 静默返回None（等同空body）。测试涉及中文内容的POST请求改用Python
  `requests.post(url, json={...})`，不要用inline `curl -d`。
- 项目里每次 `python main.py <cmd>` 实际会看到**两个python进程**（`.venv\Scripts\python.exe` +
  `Python311\python.exe`），是正常的重新拉起机制，不是重复启动/异常。
