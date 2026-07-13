# Phase 11 交付报告：热点看板增强 + 系统修复

**分支**：`feature/hot-dashboard`（已合并 Phase10 移动端代码）  
**日期**：2026-07-13  
**状态**：✅ 已提交，容器已部署验证

---

## 一、本次交付内容概览

| 类别 | 内容 | 文件 |
|---|---|---|
| 功能 | 看多热度榜时间段切换 | `Dashboard.tsx` / `overview.py` |
| 功能 | 热度榜视觉升级（排名徽章+热度条） | `Dashboard.tsx` |
| 功能 | 板块/行业点击直跳选股 | `Dashboard.tsx` |
| 功能 | 大V名字点击跳转AI总结 | `Dashboard.tsx` / `Summary.tsx` |
| 功能 | 手机端热力图优化 | `Dashboard.tsx` |
| 功能 | 日线图默认显示近1个月 | `StockDetail.tsx` |
| 功能 | 日线图雪球App跳转按钮 | `StockDetail.tsx` |
| 修复 | 实时报价不再重置K线缩放 | `StockDetail.tsx` |
| 修复 | 手机十字光标松手消失 | `StockDetail.tsx` |
| 修复 | 定时任务时区错误 | `docker-compose.yml` |
| 安全 | 10项安全加固（独立分支） | 见安全评审报告 |
| 文档 | git工作流说明 | `doc/git工作流说明.md` |
| 文档 | 应用安全评审报告 | `doc/安全评审报告_2026-07-13.md` |

---

## 二、功能详情

### 2.1 看多热度榜增强

**问题背景**：热度榜固定显示近7天数据，无法调整；榜单样式单调，行业/概念条目不可交互。

**交付内容**：

#### 时间段切换
- 后端 `/api/overview` 新增 `days` 查询参数（1~90，默认7），热度榜计算窗口随之变化
- 前端顶部加 Segmented 选择器：**今天 / 近3天 / 近7天 / 自定义**（自定义展示 InputNumber）
- 不同时间段结果独立缓存，切换秒出

#### 视觉升级
- 前3名显示金🥇银🥈铜🥉徽章，4名起显示小灰数字
- 每条目有热度进度条，宽度按相对第1名的比例缩放，右侧显示**绝对只数**（而非百分比，语义更清晰）
- 个股条目：股价/涨跌幅染色（红涨绿跌）

#### 板块/行业点击跳转选股
- 行业/概念 tab 的板块名变为蓝色可点，带 `↗` 提示，Tooltip 说明"点击筛选该板块"
- 点击后写入 `screenerState`（`sectorOn=true, sectorMode="manual", sectorNames=[板块名]`），跳转 `/screen` 并触发 `autoRun`，直接出结果

#### 大V名字点击跳转AI总结
- 热度榜里的大V名字 Tag 变为蓝色可点
- 点击跳转 `/summary` 页，通过 `location.state.userId` 传入 userId
- `Summary.tsx` 新增读取 `location.state.userId`，到达时自动预选对应大V

#### 手机端热力图
- 移动端（`useIsMobile()`）改为近12周条形图（按周聚合发帖数），无需横向滚动，信息密度更合理
- PC 端保留原始年度日历热力图，加 `overflow-x: auto` 横滑兜底

---

### 2.2 K线日线图修复与优化

#### 实时报价不再重置缩放（Bug 修复）

**根本原因**：`option` 通过 `useMemo` 依赖 `bars`，`bars` 依赖 `quote`，`quote` 每秒轮询一次，导致每秒执行一次 `notMerge` 全量图表重建，`dataZoom` start/end 被重置回初始值（45%~100%）。十字光标的 `setPanDisabled(true)` 锁定状态也因此被每秒清掉。

**修复方案**：
- `option`（传给 ReactECharts 的配置）只依赖 `kline/dark/isMobile`，kline 加载后仅构建一次
- quote 更新走独立 `useEffect`，直接调 `inst.setOption({ series: [...] })` 只更新K线和成交量两条数据，ECharts 内部增量合并，zoom 状态完全保留

#### 手机十字光标松手消失（Bug 修复）

**根本原因**：`hideTip` 只隐藏 tooltip 浮层内容，无法清除 `axisPointer: { type: "cross" }` 的两条虚线（这是 ECharts 独立绘制的准星线条）。前后共尝试三种方案：
1. `hideTip` → 清不掉虚线
2. `setOption({ axisPointer: { show: false } })` → 目标组件不对，无效
3. `rAF + setOption` → 时序问题，不稳定

**最终修复**：`hide()` 改为 `setOption({ tooltip: { axisPointer: { type: "none" } } })`，直接把准星类型切掉；下次 `showAt()` 调用前先切回 `"cross"`，用户无感知。

同时修复抬手后浏览器合成 mousemove 重新召回准星的问题：`onUp` 对所有 touch 抬手（不只 armed 态）记录时刻，`onMove` 鼠标分支200ms 内忽略。

#### 默认缩放改为近1个月
- `buildOption` 动态计算 `defaultStart`：22个交易日 / 总bar数，进页面直接看到最近1个月行情
- 数据不足22条时全显

#### 雪球 App 跳转按钮
- 标题栏新增「雪球 📱」按钮，根据股票代码前缀判断交易所（SH/SZ/BJ）
- 使用 `xueqiu://s/${symbol}` URL Scheme 唤起 App（本地服务 localhost 不在雪球域名，Universal Links 不生效，必须用 scheme）
- App 未安装时1.5秒后降级打开网页版（`window.blur` 检测 App 是否成功接管）

---

### 2.3 定时任务时区修复

**问题**：Celery beat/worker 容器使用 UTC 时间，`schedules` 表里的 `start=09:00, end=21:00` 是按北京时间填写的。容器判断为 UTC 09:00~21:00（= 北京时间17:00~次日05:00），导致北京白天（09:00~17:00）任务完全空窗。

**表现**：`beat.tick` 和 `stock.auto_sync_tick` 执行时间仅 0.002s（时间窗口判断失败直接 return）。

**修复**：`docker-compose.yml` 的 `worker` 和 `beat` 服务加入环境变量 `TZ: Asia/Shanghai`，容器时间与北京时间对齐。

验证：重启后日志时间戳由 UTC `05:57` 变为北京时间 `14:02`，`beat.tick` 执行时间升至 0.09s（正常走完逻辑）。

---

## 三、安全加固（独立交付，已合入 dev）

本轮同步完成10项安全修复，已作为独立 commit（`fix/security-hardening`）合入 `dev` 主干，不在 `feature/hot-dashboard` 分支等待功能审查。

详见：`doc/安全评审报告_2026-07-13.md`

| ID | 问题 | 等级 | 状态 |
|---|---|---|---|
| SEC-001 | OTP 使用非密码学安全随机数 | 🔴 高危 | ✅ 已修复 |
| SEC-002 | SMS/微信/邮件注册缺少限流 | 🔴 高危 | ✅ 已修复 |
| SEC-003 | JWT 密钥硬编码默认值 | 🔴 高危 | ✅ 已修复 |
| SEC-004 | `send_sms` 阻塞 event loop | 🔴 高危 | ✅ 已修复 |
| SEC-005 | `/metrics` 无鉴权暴露 | 🟡 中危 | ✅ 已修复 |
| SEC-006 | `assert` 用于生产路径 | 🟡 中危 | ✅ 已修复 |
| SEC-007 | CORS 配置过度宽松 | 🟡 中危 | ✅ 已修复 |
| SEC-008 | `/me` 串行3次 DB 查询 | 🟡 中危 | ✅ 已修复 |
| SEC-009 | `bump_dataver_sync` 无连接复用 | 🟢 低危 | ✅ 已修复 |
| SEC-010 | 帖子搜索单字符触发全表扫描 | 🟢 低危 | ✅ 已修复 |

---

## 四、分支状态

```
dev                    d0d5a64  ← 当前主干，含安全修复+热点看板
  ↑
  ├── fix/security-hardening   5d14ce2  ← 安全修复（已合入 dev，可删）
  └── feature/hot-dashboard    d0d5a64  ← 本次功能开发，待 PR → dev
```

下一步：
1. `feature/hot-dashboard` 完成测试后 PR → `dev`
2. 可删除 `fix/security-hardening`（已合入）
3. `release_v2` 落后 dev 较多，可考虑删除归档

---

## 五、已知问题 & 后续建议

### 热度榜数据问题
- **行业 tab 数据少**：新浪行业接口上次同步返回0条，需等雪球申万134行业同步完成（宿主 browser worker 跑完）才会有内容
- **卫星航天等概念不出现**：热度榜读的是AI日总结里的结构化标的表格，不是帖子全文关键词；大V只在正文泛论板块而没有具体列出个股/方向时，该板块不进统计——这是设计行为，不是 bug
- **板块成分股**：`板块成分股全量同步`（897个）需跑完才能完整映射个股→板块

### 十字光标
- 雪球跳转的 URL Scheme 路径 `xueqiu://s/SH600000` 为推测值，若 App 内显示异常可换 `xueqiu://stock?symbol=SH600000` 等格式再试

### 待做事项（来自 Phase8 候选功能 & Phase9 PRD）
- 忘记密码 / 账号绑定 / 短信接入（见 `doc/访客账号体系后续需求PRD.md`）
- 选股并发瓶颈优化（同步线程池上限，见安全评审报告 §4.2）
- JWT 吊销机制（30天 token 无法提前失效）
