# 雪球大V看板 & A股选股系统 —— Phase 10 移动端UI适配交付报告

| 项 | 内容 |
|---|---|
| 文档类型 | 阶段交付报告 |
| 周期 | 2026-07-12 |
| 状态 | 代码在工作区，**未提交**（分支 `feature/mobile-ui-polish`，从 `dev` 切出；`dev` 当前与 `feature/user-accounts` 同头，最终目标合并回 `dev`，不是 `master`） |
| 范围 | 全站移动端适配：底部Tab导航替代侧边栏、选股结果表格→卡片、信息密度风格（雪球/同花顺App风）全局收紧 |
| 关联代码 | `frontend/src/{App,index.css,hooks/useIsMobile,pages/*}.tsx` |

---

## 1. 背景

此前前端只有一套桌面布局（`Sider` 侧边栏 + `Drawer` 汉堡菜单凑合手机端），断点判断散落在 `App.tsx`(`lg`)、`Posts.tsx`(`md`)、`StockDetail.tsx`(局部 `useBreakpoint`) 三处各自为政，选股页 12 列表格在窄屏只能横向滚动。本阶段目标是做一次系统性的移动端体验改造，风格定为**信息密度风**（贴近雪球/同花顺App的紧凑感），不是极简留白风。

## 2. 变更概览

| # | 主题 | 说明 |
|---|---|---|
| 1 | 统一断点 Hook | `hooks/useIsMobile.ts`，包装 antd `Grid.useBreakpoint()`，阈值统一在 `md`(768px)，替换三处各自为政的写法 |
| 2 | 底部Tab栏导航 | 仿微信/支付宝，`App.tsx` 新增 `BottomTabBar`，窄屏隐藏 `Sider`；管理后台入口/主题切换收进 header「更多」下拉 |
| 3 | 选股结果卡片化 | `Screener.tsx` 窄屏把 12 列 Table 换成 `StockCard` 卡片列表，不用横向滚动就能看全 |
| 4 | 板块行情表格瘦身 | `SectorRank.tsx` 窄屏把 6 列压缩成 3 列（板块/涨跌合并/平均涨幅） |
| 5 | 登录页响应式 | `VisitorLogin.tsx`/`Admin.tsx` 登录表单窄屏不再固定宽度溢出屏幕 |
| 6 | 全局密度样式 | `index.css` 媒体查询统一收紧 `ant-card`/`ant-statistic`/`ant-list-item`/`ant-descriptions`/`ant-form-item` 的内边距和字号 |
| 7 | 逐页精修 | Dashboard/Summary/StockDetail/Admin/SectorRank/Screener 的标题字号、间距、按钮尺寸窄屏统一收紧 |

---

## 3. 详细变更

### 3.1 统一断点：`hooks/useIsMobile.ts`

```ts
import { Grid } from "antd";
const { useBreakpoint } = Grid;
export function useIsMobile(): boolean {
  const screens = useBreakpoint();
  return !screens.md;
}
```

全站统一在 768px 断点判断"是否手机端"，`App.tsx`/`Posts.tsx`/`Screener.tsx`/`StockDetail.tsx`/`SectorRank.tsx`/`Dashboard.tsx`/`Summary.tsx`/`Admin.tsx` 均已切换到这个 Hook。`StockDetail.tsx` 的触屏手势逻辑（长按十字光标、双指缩放）只依赖 `isMobile` 这个布尔值，换断点来源没有改变行为。

### 3.2 底部Tab栏导航（`App.tsx`）

窄屏隐藏 `Sider`，改为固定在视口底部的 `BottomTabBar`（看板/帖子流/AI总结/选股/板块行情 5 个常用只读入口），贴合 `env(safe-area-inset-bottom)` 安全区。管理后台、主题切换、账号菜单这几个次要入口挪进 header 右侧的「更多」`Dropdown`（`MoreOutlined`），因为 Tab 栏位有限放不下。`Content` 的 `paddingBottom` 窄屏下留出 `--tab-bar-height`(50px) + 12px，避免内容被悬浮 Tab 栏遮住。

确认了 oh-my-live2d（菲比助手）在移动端会自动隐藏模型本体（`mobileDisplay` 默认 `false`），只留一个贴底 80px 的小状态条，跟新的 50-60px Tab 栏没有重叠风险，未对 Live2D 相关代码做任何改动。

### 3.3 选股结果卡片化（`Screener.tsx`）

窄屏下 `StockCard` 组件替代 12 列 Table：首行名称/代码 + 最新价/涨跌幅，中间板块/概念标签换行展示（复用既有 `CollapsibleTags`），底部 3 列小表放换手率/PE/PB/市值/ROE，最后一行大V看好标签。桌面端 Table 逻辑原样保留，两者共享同一份 `rows` 状态。

### 3.4 板块行情表格瘦身（`SectorRank.tsx`）

窄屏 `columns` 分支把"成分股数/上涨/下跌"合并成一列（`23/12` 形式的涨跌数对），省下的宽度给板块名和涨幅列，去掉横向滚动。点击板块名跳转选股页的逻辑（`screenerState` 单例 + `autoRun`）未改动。

### 3.5 全局密度样式（`index.css`）

```css
@media (max-width: 767px) {
  .ant-card-body { padding: 12px !important; }
  .ant-card-head { padding: 0 12px; min-height: 40px; }
  .ant-card-head-title { font-size: 14px; white-space: normal; }
  .ant-statistic-title { font-size: 12px; }
  .ant-statistic-content { font-size: 18px; }
  .ant-list-item { padding: 8px 0; }
  .ant-descriptions-item-label, .ant-descriptions-item-content { font-size: 13px; }
  .ant-form-item { margin-bottom: 12px; }
}
```

这段全局规则覆盖了没有单独改造过的页面（比如 `Posts.tsx` 本身是自定义 `.post-card` 布局不受影响），配合各页面内联的 `isMobile ? x : y` 精修（标题字号 `level={isMobile ? 5 : 4}`、`Row gutter` 窄屏减半、按钮 `size="small"` 等），做到不用逐个组件写死样式也能统一收紧。

### 3.6 逐页精修清单

| 页面 | 改动 |
|---|---|
| `Dashboard.tsx` | 标题/大V选择器缩小；4张统计卡间距收紧；热度榜列表行间距压缩；两张图表高度 220→180；"最新动态"原帖链接窄屏挪到标题行内 |
| `Summary.tsx` | 标题/选择器缩小；Tabs 用 small 尺寸；问答卡标题窄屏简化为"AI 问答" |
| `StockDetail.tsx` | 返回按钮/标题缩小；底部三张信息卡（估值财务/大V提及/相关新闻）间距收紧 |
| `Admin.tsx` | 登录表单响应式宽度（同 VisitorLogin）；后台主界面标题/按钮/卡片间距收紧 |
| `SectorRank.tsx` | 标题/搜索框缩小 |
| `App.tsx` | header 标题超长时省略号截断，不挤到主题切换/账号按钮 |

---

## 4. 验证记录

- 每一批改动后都跑过 `npm run build`（`tsc -b && vite build`），全部通过，仅有改动前就存在、与本次无关的 chunk 体积警告（antd ~1.2MB / echarts ~1.05MB / index ~1MB，未做代码分割）。
- 每一批改动后都用 `docker compose up -d --build frontend`（只重建 frontend 服务，规避"只重建依赖服务不重启 nginx 容器"导致的 DNS 缓存 502，详见 `doc/debug/2026-07-12_管理员登录502.md`）重建容器，`curl` 验证 `/` 200、`/api/overview` 401（代理链路正常，401 是预期的登录墙响应）。
- **未验证**：真机/浏览器 DevTools 移动模拟器下的人工视觉走查（各页面在 iPhone/Android 常见分辨率下的实际渲染效果、Tab 栏与 Live2D 是否真的不重叠、选股卡片在极端数据下的换行表现）；暗色模式下这批改动的对比度；横屏模式。

---

## 5. 后续前端美化方向

以下是这次改造之外，观察到的、值得下一步投入的方向，按"性价比高→低"大致排序，不是必须按顺序做。

### 5.1 骨架屏替代全屏 Spin（推荐先做，性价比高）

当前 `Dashboard.tsx`/`Screener.tsx` 等页面加载时用 `<Spin spinning={isLoading}>` 整块遮罩，数据到来前是空白+转圈。大厂 App 基本都用骨架屏（灰色占位块模拟卡片/列表轮廓），感知加载速度更快、也更"信息密度风"。antd 自带 `Skeleton` 组件，改动量不大：给 Dashboard 的统计卡、热度榜列表、Screener 的结果区各配一版骨架屏即可。

### 5.2 硬编码颜色收敛进设计变量

`index.css` 已经建立了 `--text-secondary`/`--link-h3` 等 CSS 变量体系，但组件里仍有不少内联硬编码色值散落各处（如 `Dashboard.tsx`/`Admin.tsx`/`VisitorLogin.tsx` 里的 `"#888"`/`"#666"`/`"#cf1322"`），这些在暗色模式下不会跟着变量联动，视觉上会有轻微不一致（比如暗色模式下 `#888` 可能偏暗看不清）。建议排查一遍，统一替换成 `var(--text-secondary)` 等既有变量，需要新颜色（如涨跌色）再补几个语义变量。

### 5.3 长列表虚拟化

选股结果无上限（`limit: 300`），`Screener.tsx` 窄屏用 antd `List` 分页展示、桌面端 Table 也是客户端分页，都不是虚拟滚动。300 条数据在手机端全量渲染问题不大，但如果以后放开 `limit` 或做"大V提及"这类可能上千条的列表，需要上 `react-window` 之类的虚拟滚动，避免长列表卡顿。当前规模下优先级不高，先记录。

### 5.4 图表主题统一

`Dashboard.tsx`/`StockDetail.tsx` 里 echarts 的颜色（涨跌红绿、MA5/10/20 配色、坐标轴颜色）是各图表内联散写的（`axisTextColor`/`UP`/`DOWN` 等局部常量），没有抽成一份全站共享的 echarts theme。图表一多容易出现配色不一致或改一处漏改一处。可以抽一个 `echartsTheme.ts`，用 `echarts.registerTheme` 统一注册亮/暗两套，各图表 `option` 只管数据不管配色。

### 5.5 空状态与错误态精细化

目前空数据/加载失败统一用 antd `<Empty description="...">`，文案够用但视觉比较朴素。大厂App通常给"暂无数据"配一张小插图或图标，区分"真的没数据"和"接口出错"两种语气（后者一般会给"重试"按钮）。这个是纯视觉投入，性价比中等，可以在核心页面（看板、选股结果）先做。

### 5.6 页面切换过渡动效

当前路由切换是硬切，没有过渡动画。可以给 `Content` 加一个轻量的 fade/slide 过渡（`react-router` + CSS transition 或引入 `framer-motion`），配合底部Tab栏切换会更有"App感"。注意 Live2D 单例挂载逻辑对 DOM 结构变化比较敏感（见 CLAUDE.md 踩过的坑），引入动画库前要验证不会触发菲比重复初始化。

### 5.7 下拉刷新手势

移动端常见的"下拉刷新"目前没有，只能等 TanStack Query 的自动 refetch 或手动跳路由。如果要做，可以在几个核心只读页面（看板/帖子流）加一个轻量下拉刷新组件，触发 `queryClient.invalidateQueries`。这个跟 StockDetail 现有的触屏手势（长按/双指缩放）要注意手势冲突（下拉刷新一般只在页面顶部触发，K线图在自己卡片内部，冲突概率低但要验证）。

### 5.8 无障碍性（Accessibility）梳理

目前没有做过系统性的 a11y 检查：图表/图标是否有 `aria-label`、颜色对比度（尤其涨跌红绿色，色盲用户可能分不清涨跌，纯靠颜色区分有风险）、键盘导航（Tab 栏当前是纯 `onClick` 的 `div`，没有 `role="tab"`/键盘可达性）。这块投入产出不直接体现在"好看"上，但是专业度的体现，建议至少把涨跌色配色调整成同时有符号（`+`/`-`已经有了，这点做得对）+ 颜色的双重编码，已经具备；Tab 栏补语义化标签是低成本高价值的一项。

### 5.9 首屏加载性能（chunk 分割）

`npm run build` 一直有的警告：antd/echarts/index 三个 chunk 都超过 500KB。虽然跟本次移动端改造无关，但移动端用户对首屏体积更敏感（弱网/流量场景）。可以用 `vite.config.ts` 的 `build.rollupOptions.output.manualChunks` 把 antd/echarts 拆成独立 chunk，配合路由级 `React.lazy` 懒加载非首屏页面（比如 `Admin.tsx` 管理后台大部分用户永远不会访问，没必要打进首屏包）。

### 5.10 PWA 体验升级

CLAUDE.md 和 Phase8 规划里提到的 `sw.js` 目前是"可安装"级别的极简实现。如果移动端是主要使用场景，可以考虑加上启动画面（`manifest.json` 的 `splash_screens`/主题色）、离线兜底页、以及 Phase8 里提到过、当时判断"往后放"的 Web Push 通知（周总结生成完成提醒）。这个投入较大，建议放最后。

---

## 6. 建议的开工顺序

**第一批（性价比最高，一次会话可完成）**：5.1（骨架屏）→ 5.2（硬编码颜色收敛）→ 5.5（空状态精细化）。三项都是局部视觉改动，不涉及架构调整，风险低。

**第二批**：5.4（echarts 主题统一）→ 5.9（chunk 分割/懒加载）。前者需要梳理现有图表配色，后者需要验证懒加载不影响 Live2D/路由守卫逻辑。

**第三批（需要更谨慎设计）**：5.6（过渡动效，需验证 Live2D 兼容）→ 5.7（下拉刷新，需验证手势冲突）→ 5.3（虚拟滚动，当前规模非必需）→ 5.8（a11y 梳理）→ 5.10（PWA 升级）。

## 7. 部署清单（下次会话开工前）

1. 本次改动全部在工作区，尚未 `git commit`——先确认改动符合预期再提交，提交后合并回 `dev`。
2. `docker compose up -d --build frontend`（只有 frontend 变了，api/worker/beat 不需要重建）。
3. 浏览器人工走查（本阶段唯一缺失的验证）：至少用 Chrome DevTools 移动模拟器过一遍 App/Dashboard/Posts/Summary/Screener/SectorRank/StockDetail/Admin/VisitorLogin 九个页面，重点看 Tab 栏与 Live2D 是否重叠、选股卡片长内容换行、暗色模式对比度。
4. 确认 `dev` 分支的合并目标和时机（当前 `dev` 与 `feature/user-accounts` 同头，访客账号系统那批改动的部署清单——见 `doc/Phase9访客账号系统交付报告.md` 第6节——也还没走完，两者合并顺序需要和用户确认）。
