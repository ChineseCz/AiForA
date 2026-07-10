# 雪球大V看板 & A股选股系统 —— Phase 6 产品化与体验优化交付报告

| 项 | 内容 |
|---|---|
| 文档类型 | 阶段交付报告（在 Phase 1–5 服务化重构结项之后的产品化迭代） |
| 版本 | v1.0 |
| 周期 | 2026-07-09 ~ 2026-07-10（结项后至本次同步） |
| 状态 | 代码已完成，**尚未提交/未容器化验证**（见第 6 节） |
| 范围 | K线前复权、AI总结与选股联动、帖子流改版、Live2D 助手「菲比」、移动端与暗色模式、K线图表交互重做 |
| 关联代码 | `backend/app/services/{adjust,summarizer,matching,screen_api}.py`、`frontend/src/{App,main,theme,live2d,pageContext}.ts(x)`、`frontend/src/pages/*` |

---

## 1. 背景

《服务化重构分阶段结项总结》完成后，架构层面（FastAPI/Postgres/Redis/Celery/PgBouncer + React 前端）已经落地并验收通过。本轮迭代不再是架构改动，而是**上线前的产品化打磨**：修正一处数据正确性问题（K线不复权），并围绕"好不好用"补齐移动端、暗色模式、图表交互、AI 助手联动等体验短板。全部改动集中在 `backend/app/services/*` 与 `frontend/src/*`，未触及数据库表结构、队列拓扑等架构决策。

---

## 2. 变更概览

| 主题 | 触发原因 | 影响范围 |
|---|---|---|
| K线前复权 | 新浪K线接口给的是不复权价，除权除息日价格跳空，MA/MACD/KDJ 全部失真 | 后端K线回补 + 一次性历史数据迁移脚本 |
| AI总结 ↔ 选股联动 | 总结里"看多/看空"判断和选股筛选是两套孤立功能 | summarizer/matching/screen_api |
| 选股入口放宽 | 只想按"大V提及"或"板块"筛选时被迫先凑一个无意义的预设条件 | screen_api |
| 帖子流改版 | 原表格列表丢失了雪球原生的图文信息 | posts 仓储 + Posts 页面 |
| Live2D 助手「菲比」 | 管理后台缺少交互亮点 | 新增 live2d/FeibiWidget + summarizer 新接口 |
| pageContext | 菲比要"看懂"用户当前在哪个页面 | 新增跨页面单例 |
| 选股状态持久化 | 详情页返回后筛选条件/结果丢失 | 新增 screenerState 单例 |
| 暗色模式 + 移动端导航 | 无暗色支持，窄屏侧边栏直接消失 | theme.tsx + 全局布局 |
| K线图表交互重做 | 移动端手势与信号标记体验差 | StockDetail.tsx（本轮改动量最大，378 行） |

---

## 3. 详细变更

### 3.1 K线前复权（数据正确性修复）

- **问题**：`quotes.sina.cn` 返回的历史K线是不复权价格，遇到除权除息（分红/拆股）当天会出现价格断崖，直接污染 MA5/10/20、MACD、KDJ 等技术指标，进而影响选股预设策略（`ma_cross`/`golden_cross` 等）的判断。
- **方案**：
  - `services/external/sina.py` 新增 `fetch_qfq_factors(code)`，用纯 `requests` 拉取新浪 `qfq.js` 的"除权日 → 累计复权因子"稀疏表（不走浏览器反爬流程，成本很低）。
  - 新增 `services/adjust.py::compute_qfq(bars, factors)`：二分查找每根K线对应的最新因子，把 OHLC 除以因子得到前复权价；找不到因子的日期原样返回，不报错。
  - `scrapers/kline.py::backfill_history` 落库前调用上述两步；因子拉取失败不阻塞回补主流程（per-item 容错，遵循既有原则）。
  - `repositories/sync_data.py::save_history_bars` 的写入语义从"只补空 open"改为**整行覆盖 OHLC/volume**——因为前复权价会随未来新的除权事件变化，同一天的数据必须能被覆盖重算，不能只写一次就锁死。
  - 新增一次性迁移脚本 `backend/scripts/adjust_existing_kline.py`：对 `stock_daily` 表里已入库的历史数据逐股票拉因子、转换、写回，再触发一次指标预计算重算，修正上线前已经攒下的不复权历史数据。
- **风险点**：`save_history_bars` 写入语义变更影响所有历史K线的写入路径，且新增了一个需要手动运行一次的迁移脚本——**这两点在容器化环境里还没有跑过端到端验证**，建议在合入前对着预计算指标表做一次新旧结果对拍。

### 3.2 AI总结与选股联动

- 总结表格从 4 列（名称/代码/方向/理由）简化为 3 列（名称/方向/理由），并在 prompt 里约束"方向"只能四选一；因大模型偶尔不遵守格式，加了正则 `_strip_direction_header_note` 兜底清理表头多余说明。
- 新增 `matching.parse_bullish_names`：按表头文字定位列（不依赖列序号，兼容新旧两种表结构），从总结 markdown 里抽出被判定"看多"的标的。
- 新增 `matching.filter_bullish` + `repositories/sync_data.get_recent_daily_summaries`：选股页新增"只看大V看多"开关，在常规"提及"过滤基础上再叠加"最近 N 天总结中被判定看多"的条件。
- **缓存 bug 修复**：`workers/tasks/summarize.py` 的定时任务在 `job_run` 中补上 `invalidate_cache=True`——此前手动 regen 总结后 DB 已更新但 Redis 缓存不会失效，页面要等 TTL 自然过期才能看到新内容。

### 3.3 选股入口放宽

`screen_api.screen` 不再强制要求"预设策略"或"筛选条件"其中之一：只勾选"大V提及"或"板块"也能直接跑（此时用全市场最新行情作为候选池，再交给后续过滤缩小范围）；多层过滤叠加后在末尾统一 `rows[:limit]` 截断，避免超出声明的返回条数。

### 3.4 帖子流改版

- `repositories/posts.py::get_posts` 新增 `images` 字段解析，兼容历史迁移数据里"多个 URL 逗号拼接成一个字符串"的脏数据。
- `Posts.tsx` 从表格改成仿雪球动态的卡片流（头像/正文/配图/点赞转发评论收藏/原帖链接），并按 `Grid.useBreakpoint` 做移动端布局适配。

### 3.5 Live2D 助手「菲比」

新增管理后台专属的二次元虚拟助手（代号"菲比"），挂在页面右下角，点击弹出聊天抽屉，可基于当前页面上下文与站长多轮问答（不做投资建议）。

- 后端：`summarizer.py` 新增 `FEIBI_SYSTEM_PROMPT` 人设 + `ask_feibi(history, question, page_context)`；`api/routers/admin/jobs.py` 新增 `POST /api/admin/feibi/ask`，历史消息只信任 `role`(user/assistant)/`content` 两个字段，最多留 20 轮，`page_context` 截断到 1000 字防 prompt 注入。
- 前端：`live2d.ts` 用模块级单例封装第三方库 `oh-my-live2d`（新依赖，`package.json` 已加）加载 8 个官方示例模型资源（`frontend/public/live2d/`）；`FeibiWidget.tsx` 是聊天抽屉组件，登录后才渲染。
- **踩坑记录**：`oh-my-live2d` 切换模型只把旧模型摘出舞台、不释放 WebGL 纹理，连续切换约 5 次后纹理槇耗尽导致后续切换必定失败。因无法改 `node_modules`，改为切换前手动调用旧模型的 `.destroy()` 抢救；另外 React StrictMode 下 effect 双调用会导致挂载两份模型，改用模块级单例规避。

### 3.6 pageContext（跨页面上下文）

新增 `pageContext.ts`：模块级单例 + `usePageContext(text)` hook，让 Dashboard/Posts/Summary/Screener/StockDetail 五个页面把"用户当前在看什么"注册为一段文本，供菲比提问时作为背景信息带给后端。与 Live2D 状态一样脱离 React 树（挂在 body 上），未使用 Context/Provider。

### 3.7 选股状态持久化

新增 `screenerState.ts`：模块级单例保存选股页全部筛选条件与结果行。因为从股票详情页返回时 `Screener` 组件会重新 mount，纯 `useState` 保存不住，改用该单例作初始值来源并在状态变化时 `useEffect` 同步写回，解决"筛选后进详情页再返回，筛选结果丢失"的问题。

### 3.8 暗色模式 + 移动端导航

- 新增 `theme.tsx::ThemeModeProvider`/`useThemeMode`：读本地存储或系统偏好决定亮/暗模式，写入 `<html data-theme>` 并持久化；`main.tsx` 联动 antd 的 `darkAlgorithm`/`defaultAlgorithm`；`index.css` 改用一套亮暗两态的 CSS 变量取代硬编码颜色。
- `App.tsx` 新增顶部 Header（暗色切换按钮 + 移动端汉堡菜单，用 `Drawer` 展示侧边导航），替代原来窄屏下 `Sider` 直接消失的方案。
- `Dashboard.tsx` 热力图从连续渐变色改为仿 GitHub 贡献图的离散色阶，并适配暗色模式坐标轴/网格线颜色。

### 3.9 K线图表交互重做（StockDetail.tsx，改动量最大）

- 买卖点标记从 `markPoint` 改为独立 `scatter` 系列（三角符号 + 固定像素偏移），解决多信号命中同一根K线重叠、以及百分比偏移随缩放忽大忽小的问题。
- 新增常驻 `InfoBar`（日期/OHLC/涨跌幅/MA5/10/20）与 `SubIndicatorLabels`（成交量/MACD/KDJ数值），取代原来只能鼠标悬浮才看到的 tooltip。
- 关闭 echarts 自带 tooltip 自动触发，改为手动 `dispatchAction` 驱动：桌面端 hover 立即显示；触屏端"长按 500ms 才显示十字光标，期间位移超阈值则判定为划动并放弃"，解决之前设置压制打不过 echarts 内部触发时机的问题。
- 手机端接管双指缩放（pinch）手势：自算真实 `pinchScale` 幅度并加阻尼系数，替代 echarts 内置的"固定每次缩 10%"。
- 补充暗色模式（坐标轴/图例/网格线随主题切换）与移动端布局适配（图表高度/留白/字号随 `isMobile` 调整）；接入 `usePageContext`，把当前股票/hover的K线/估值指标/所属板块喂给菲比。

### 3.10 其它细节

- `Admin.tsx`：AI总结面板新增"强制重新生成"（`regen`）勾选框，卡片布局改响应式。
- `Summary.tsx`：日期列表从常驻 List 改为可收起的 `Collapse`，复用新增的 `MarkdownContent.tsx` 组件；默认选中大V从"列表第一个"改为优先选"冰冰小美"（存在则选中）。
- `MarkdownContent.tsx`（新增）：给总结渲染出的 HTML 表格统一加横向滚动容器，移动端按表头文字（非列序号）删掉"代码"列，兼容新旧表结构。
- `hooks.ts`/`types.ts`：新增 `bullish_only`（选股请求）、`images`（帖子）类型字段。

---

## 4. 关键设计取舍

1. **前复权因子按需拉取而非离线预生成**：因子表数据量小（每股仅除权除息日有记录），实时拉取成本可接受，避免再建一张同步表。
2. **跨页面单例而非 React Context**：Live2D 挂载点、菲比状态、pageContext、screenerState 均脱离 React 组件树生命周期（挂在 `body` 或纯模块作用域），是因为它们要跨路由跳转存活，比 Context/Provider 更省心，代价是失去了 React 的响应式追踪，需手动 `useEffect` 同步。
3. **echarts 手动 dispatchAction 而非依赖内置交互**：触屏长按/pinch 的产品需求超出了 echarts 默认交互能力边界，选择犧牲一部分"用官方 API"的简洁性换取可控的手势体验。
4. **第三方库 bug 绕过而非 fork/patch**：`oh-my-live2d` 的纹理释放缺陷通过应用层手动 `.destroy()` 抢救，而非 fork 或 patch-package，保持依赖可正常 `npm update`。

---

## 5. 风险与遗留

| 项 | 说明 | 建议 |
|---|---|---|
| 前复权写入语义变更未端到端验证 | `save_history_bars` 从"补空"改"整行覆盖"，影响所有历史K线写入路径 | 合入前跑一次预计算指标表新旧对拍 |
| `adjust_existing_kline.py` 一次性迁移未在生产数据上跑过 | 脚本改写线上历史行情数据，不可逆 | 先在数据库快照/副本上跑一遍，确认行数与关键股票抽查后再上线执行 |
| Live2D 资源体积 | `frontend/public/live2d/` 新增 8 个模型资源目录 | 确认最终只保留会用到的模型，避免打包体积膨胀 |
| 菲比接口的 prompt 注入防护 | 仅做了长度截断，未做内容过滤 | 后续如接入更强模型，评估是否需要额外的输入清洗 |
| 全部改动均未提交 | 当前分支 `release_v2` 处于未 commit 状态 | 提交前建议按主题拆分为多个 commit，而非一次性大 commit |

---

## 6. 验证情况

本轮所有改动**均未经过容器化端到端验证**（docker compose 未重启、未跑对拍脚本、前端未过 `npm run build`）——纯代码调研整理，未做验证性操作。合入前至少应完成：

- `npm run build` 类型检查 + 构建。
- 后端 `alembic`/容器启动，人工过一遍选股"只看看多"、K线图表移动端手势、菲比问答。
- `adjust_existing_kline.py` 在非生产环境跑一遍并抽查复权后价格。

---

## 7. 相关文档

- 架构与五阶段结项：`doc/服务化重构分阶段结项总结.md`
- 方案设计与 Phase 1 详情：`doc/服务化重构技术方案与Phase1交付报告.md`
- 运行手册：`backend/README.md`
