# Phase 12 交付报告：选股策略参数化 + 新策略 + 股票AI解读

> 分支：`feature/screening-strategy`  提交：`f261f14`  日期：2026-07-16

---

## 一、本次交付概览

| 模块 | 改动 |
|---|---|
| 选股策略 | 4个既有策略全面参数化；新增6个买点策略 |
| 技术指标 | 新增 RSI / 布林带计算；5个新指标度量函数 |
| 安全 | 参数白名单+范围裁剪，防超大窗口 DoS |
| 选股前端 | 策略卡展开参数调整面板（Collapse）；选股结果增加 AI 解读按钮 |
| 股票AI解读 | 新增服务+接口；StockDetail 增加 AiAnalysisCard |

---

## 二、选股策略参数化

### 2.1 既有策略参数化

`backend/app/services/screening.py` 为4个既有策略新增参数支持：

| 策略 key | 可调参数 | 默认值 |
|---|---|---|
| `ma_cross` / `ma_cross2` | ma_fast, ma_mid, ma_slow, cross_days, rise_days, rise_pct | 5/10/20, 3, 5, 0.03 |
| `golden_cross` | macd_fast, macd_slow, macd_signal, kdj_window, cross_days, require_both | 12/26/9, 9, 4, true |
| `fund_ok` | net_profit_yoy_min, eps_min, roe_min, revenue_yoy_min, gross_margin_min | 0/0.1/3/10/10 |

**快路径保留原则**：参数与默认值相同时仍走预计算快路径（读 `stock_indicator` 表）；自定义参数时跳过快路径，走现算。

### 2.2 参数安全校验

新增 `sanitize_strategy_params()`：
- 白名单过滤（`_PARAM_BOUNDS` 字典定义每个参数上下界）
- 非法类型/超界值回退默认值
- `require_both` 等 bool 参数单独处理

防止恶意请求传入超大周期把 O(n·窗口) 计算拖成 DoS。

---

## 三、新增6个买点策略

| 策略 key | 中文名 | 逻辑 | 核心参数 |
|---|---|---|---|
| `volume_breakout` | 放量突破 | 收盘突破近N日最高价 + 成交量>均量×倍数 | breakout_days=20, volume_mult=1.5 |
| `pullback_low_volume` | 缩量回踩 | 近期曾放量上涨，现价回踩均线±2%，近期量能萎缩 | lookback_days=10, ma_period=20, near_pct=0.02, low_volume_mult=0.7 |
| `boll_breakout` | 布林带收口突破 | 近60日带宽处于低位（分位≤30%），今日上穿上轨 | period=20, mult=2.0, squeeze_days=60, squeeze_pct=0.3 |
| `rsi_oversold_bounce` | RSI超卖反弹 | RSI从阈值下方回升到阈值上方 + 今日收阳 | period=14, threshold=30, lookback_days=2 |
| `turnover_surge` | 换手异动 | 换手率>阈值 且 涨幅在区间内（排除涨停） | turnover_min=5, change_pct_min=4, change_pct_max=9.5 |
| `volume_price_up` | 量价齐升 | 连续N日成交量与收盘价同步递增 | streak_days=3 |

> 全部为买点策略，无卖点新增。

---

## 四、指标计算层扩展（indicators.py）

新增纯计算函数：

- `compute_rsi(closes, period=14)` — Wilder 平滑 RSI
- `compute_boll(closes, period=20, mult=2.0)` — 布林带 mid/upper/lower
- `volume_breakout_metrics(bars, breakout_days, volume_mult)` — 放量突破
- `pullback_low_volume_metrics(bars, ...)` — 缩量回踩
- `boll_squeeze_breakout_metrics(bars, ...)` — 布林带收口突破
- `rsi_bounce_metrics(bars, period, threshold, lookback_days)` — RSI超卖反弹
- `volume_price_up_metrics(bars, streak_days)` — 量价齐升

`compute_macd`、`compute_kdj`、`ma_cross_metrics`、`golden_cross_metrics` 参数化（默认值不变，旧逻辑兼容）。

---

## 五、选股前端（Screener.tsx）

- 策略卡由4个扩展到10个，选中后展开 Collapse 参数面板
- `strategyParams` 状态跨路由存活（存入 `screenerState` 单例）
- 发送 `strategy_params` 字段到后端，未修改的策略不传参（走快路径）
- 选股结果表格和股票卡均新增「AI解读」按钮，点击弹出 Modal 按需生成分析

---

## 六、股票 AI 解读

### 后端

新文件 `backend/app/services/stock_ai.py`：
- 拉取该股近30条K线、最新财务数据
- 组装 Prompt 调用 LLM（通过 relay API）
- 返回 `{content, html}`

新接口（`stocks.py`）：
- `GET /api/stock/ai-analysis?code=xxx` — 读当日缓存，无缓存返回 `{generated: false}`
- `POST /api/stock/ai-analysis/generate?code=xxx` — 调用 LLM 生成，写入缓存（按交易日）

缓存策略：key = `natapp:ai_analysis:{trade_date}:{code}`，同一交易日全用户共享结果，不重复调用 LLM。

### 前端

- `StockDetail` 页底部新增 `AiAnalysisCard` 组件（自动读缓存，首次点击生成）
- `Screener.tsx` 每个股票卡/表格行新增 `StockAiAnalysisButton`（Modal懒加载）
- 新增 hooks：`useStockAiAnalysis`、`useGenerateStockAiAnalysis`

---

## 七、API 变更

| 路径 | 变更 |
|---|---|
| `POST /api/screen` | body 新增可选字段 `strategy_params: {[key]: {[param]: value}}` |
| `GET /api/stock/ai-analysis` | 新增 |
| `POST /api/stock/ai-analysis/generate` | 新增 |

后端 `config.py` 新增：
- `cache_ttl_ai_analysis`（默认86400s，按交易日缓存）
- `relay_api_key` 已有，无需新增

---

## 八、待办 / 已知限制

- 新增策略不在预计算表（`stock_indicator`）中，始终走现算，每次选股会循环全量历史K线（约4000支×N根）
- `turnover_surge` 只需快照数据，最快；其余新策略依赖历史K线，并发请求较多时会有压力
- 日线图信号参数调整（StockDetail）将在下一轮（Phase 12 续）实现

---

## 九、部署注意

本次无数据库 migration，无需 `alembic upgrade`。

1. 重建后端镜像：`docker compose build api worker`
2. 更新前端：`docker compose build frontend`
3. 重启服务：`docker compose up -d api frontend`
