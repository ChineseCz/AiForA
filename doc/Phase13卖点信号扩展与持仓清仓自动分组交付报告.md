# Phase 13 交付报告：卖点信号策略扩展 + 持仓/清仓自动分组

> 分支：`feature/screening-strategy`　基线：`2f87e7e`　日期：2026-07-22

---

## 一、本次交付概览

| 模块 | 交付内容 |
|---|---|
| 选股策略 | 新增 4 个卖点策略（MA 死叉 / 跌破均线 / RSI 超买回落 / 高位放量阴线） |
| 买点策略增强 | `ma_cross` / `ma_cross2` 新增 `first_day` 参数，支持筛选"首日出信号"个股 |
| 技术指标 | `indicators.py` 新增 6 个函数（2 个逐日信号序列 + 4 个时点度量版） |
| K 线信号 | kline 接口新增 `break_ma_ok` / `high_vol_drop_ok` 两个逐日卖点字段 |
| StockDetail | 信号面板新增 2 个卖点信号项，SP 参数扩充 4 个可调字段 |
| 选股↔详情导航 | 从选股页进入详情后，返回按钮精确导回选股页 |
| 自选股分组 | 新增「持仓」「清仓」两个系统保留自动分组，按访客账号隔离 |
| 数据库 | migration `0014`：`stock_groups` 增加 `user_id` 列 + 复合唯一约束 |
| 交易统计 | `TradeStats` 新增 `total_stocks` 字段，胜负统计口径从「按笔」改为「按股」 |
| 自选股成员 | 成员名称改为可点击链接，直达 StockDetail |

---

## 二、卖点选股策略（4 个新增）

`backend/app/services/screening.py` 新增 4 个策略函数，与既有买点策略同构（读最新快照 → 过滤 ST/S/无量 → 加载 K 线序列 → 调用 `indicators.*_metrics` → `_sorted_hits`）。

| 策略 key | 中文名 | 触发逻辑 | 核心参数 | 默认值 |
|---|---|---|---|---|
| `sell_ma_death_cross` | MA 死叉卖点 | 近 N 日内 MA5 下穿 MA10 | `cross_days` | 3 |
| `sell_break_ma20` | 跌破均线卖点 | 收盘从均线上方穿破到下方 | `ma_period` | 20 |
| `sell_rsi_overbought` | RSI 超买回落 | RSI 由 >阈值 回落至 ≤阈值 | `period`, `threshold`, `lookback_days` | 14, 70.0, 2 |
| `sell_high_volume_drop` | 高位放量阴线 | 均线上方 + 当日阴线 + 量 > 均量×倍数 | `ma_period`, `volume_lookback`, `volume_mult` | 20, 20, 1.5 |

均已注册至 `_PRESET_STRATEGIES`，新增对应 `_XXX_DEFAULTS` 默认参数字典。`_PARAM_BOUNDS` 补充 `volume_lookback: (2, 120)`，`_BOOL_PARAMS` 补充 `first_day`，复用既有 `sanitize_strategy_params` 参数白名单校验。

---

## 三、买点策略增强：`first_day` 过滤模式

**背景**：`ma_cross` / `ma_cross2` 默认判断"近 N 日内发生过金叉"，在震荡市中会持续捞出同一批票；`first_day=true` 模式改为"今天恰好是信号触发的第一天"，筛选结果更聚焦于当日新信号。

**实现**：两个策略函数新增 `first_day` bool 参数（默认 `false`，行为与历史一致）。
- `first_day=false`（默认）：沿用原 `ma_cross_metrics` 逻辑，读预计算快路径。
- `first_day=true`：调用 `indicators.daily_signal_series`，取严格序列（`strict_series`）或宽松序列（`loose_series`），要求 `series[-1] == True and series[-2] == False`（昨天未触发、今天触发），跳过预计算快路径，始终现算。

**预计算快路径判定**逻辑同步更新：仅在非 `first_day` 且其他参数均为默认值时才命中缓存。

---

## 四、技术指标层扩展（`indicators.py`）

新增 6 个函数，分两类：

### 逐日信号序列（供 K 线图逐根标记）

| 函数 | 信号语义 | 核心参数 |
|---|---|---|
| `daily_break_ma_series(bars, period=20)` | 当日收盘从均线上方穿破到下方 | `period` |
| `daily_high_volume_drop_series(bars, ma_period=20, volume_lookback=20, volume_mult=1.5)` | 当日高位放量阴线 | `ma_period`, `volume_lookback`, `volume_mult` |

### 时点度量函数（供选股用，判定"当前时点是否满足条件"）

| 函数 | 判定逻辑 |
|---|---|
| `ma_death_cross_metrics(bars, cross_days=3)` | 近 `cross_days` 日内 MA5 下穿 MA10 |
| `break_ma_metrics(bars, ma_period=20)` | 最新 K 线收盘从均线上方穿破到下方 |
| `rsi_overbought_metrics(bars, period=14, threshold=70.0, lookback_days=2)` | 近 `lookback_days` 日内 RSI 由 >阈值 回落至 ≤阈值 |
| `high_volume_drop_metrics(bars, ma_period=20, volume_lookback=20, volume_mult=1.5)` | 当日：收盘在均线上方 + 阴线 + 量 > 均量×倍数 |

调用关系：`daily_break_ma_series` / `daily_high_volume_drop_series` → `views.py`（K 线图）；`ma_death_cross_metrics` 等 4 个度量函数 → `screening.py`（选股）。

---

## 五、K 线图信号扩展（`views.py` + kline 接口）

`get_kline_view(code, sp)` 新增两组可通过 `sp` 覆盖的参数：
- `break_ma_period`（默认 20）
- `hvd_ma_period` / `hvd_volume_lookback` / `hvd_volume_mult`（默认 20 / 20 / 1.5）

输出 `KlineBar` 新增两个 boolean 字段：

| 字段 | 含义 |
|---|---|
| `break_ma_ok` | 当日是否跌破均线止损信号 |
| `high_vol_drop_ok` | 当日是否高位放量阴线卖点 |

遵循既有缓存约定：自定义参数跳过缓存，默认参数走缓存。`frontend/src/api/types.ts` 的 `KlineBar` 类型同步增加上述两个字段。

---

## 六、StockDetail 信号面板扩展

`SIGNALS` 数组新增 2 个卖点信号项：

| 字段 | 中文名 | 颜色 |
|---|---|---|
| `break_ma_ok` | 跌破均线止损 | `#f43f5e` |
| `high_vol_drop_ok` | 高位放量阴线 | `#dc2626` |

`SP_DEFAULTS` 补充 `break_ma_period: 20, hvd_ma_period: 20, hvd_volume_lookback: 20, hvd_volume_mult: 1.5`；`SP_FIELDS` 新增「跌破均线」「放量阴线」两个参数调整分组。与既有信号面板（基础指标 / 买点 / 卖点三类折叠、legend 增量更新、参数变更保持缩放范围）机制完全复用，无框架层改动。

---

## 七、选股结果 ↔ 股票详情返回导航修复

**问题**：从选股结果进入 StockDetail 后，返回按钮依赖 `navigate(-1)`，遭遇多层内部跳转时无法精确回到选股页。

**方案**：通过 React Router `state` 传递来源标识，在 StockDetail 侧精确判断。

- `Screener.tsx`：`StockCard` 卡片和结果表格"名称"列两处链接统一改为 `<Link to={...} state={{ from: "screener" }}>` 传递来源。
- `StockDetail.tsx`：`goBack()` 改为三段优先级判断：
  1. `location.state?.from === "screener"` → `navigate("/screener")`
  2. `canGoBack` → `navigate(-1)`（原有逻辑兜底）
  3. 否则 → `navigate("/screener")`

---

## 八、持仓/清仓自动分组

### 8.1 需求背景

自选股按持仓状态维护两个系统分组，随交易记录写操作实时同步，按访客账号隔离：
- **持仓**：当前 `hold_qty > 0` 的股票
- **清仓**：近 7 天内发生过"卖光"事件且当前仍为空仓的股票

### 8.2 数据库变更（migration `0014`）

`backend/alembic/versions/0014_user_id_for_groups.py`：

| 操作 | 详情 |
|---|---|
| 删除旧约束 | `name UNIQUE` |
| 新增列 | `user_id VARCHAR(100)` 可空，索引 `ix_stock_groups_user_id` |
| 新增约束 | 复合唯一 `uq_stock_groups_user_name (user_id, name)` |

管理后台全局分组（`user_id IS NULL`）不受影响，旧数据无需迁移。

### 8.3 核心逻辑（`repositories/groups.py`）

**`sync_auto_groups(session, user_id)`**：
1. 按时间正序拉取该用户全部 `trade_records`
2. 均本成本法逐笔重放，追踪每只股票 `hold_qty` 及最近一次清零日期
3. 计算 `held`（当前持仓）/ `recently_cleared`（7 天内清仓且当前为空仓）
4. `_get_or_create_group_id` 获取或创建「持仓」「清仓」分组，`_replace_members` 全量幂等替换成员

**保留名机制**：`_RESERVED_NAMES = ("持仓", "清仓")`，`POST /api/groups` 时如名称命中则返回 400。

**同步触发**：`api/routers/public/trades.py` 中 `create_trade` / `delete_trade`（成功时）/ `bulk_import_trades` 三处写操作后内联同步调用，保证操作完成立即可见，无需周期任务。

### 8.4 API 变更（groups 路由）

全部端点改为 `Depends(require_visitor)`（原 `GET .../members` 为匿名可访问，现统一要求登录）：

| 路径 | 变更 |
|---|---|
| `GET /api/groups` | 需登录；结果按 `user_id` 隔离（含全局分组 `user_id IS NULL`） |
| `POST /api/groups` | 需登录；保留名返回 400 `「{name}」为系统保留分组名，不可手动创建`；重名返回 400 |
| `DELETE /api/groups/{group_id}` | 需登录；按 `user_id` 限定范围，不可跨账号删除 |
| `GET /api/groups/{group_id}/members` | 需登录（原匿名） |

### 8.5 前端（`My.tsx`）

`AUTO_GROUP_NAMES = new Set(["持仓", "清仓"])` 常量驱动保护逻辑：
- 成员列表：隐藏"删除成员"按钮
- 分组列表：删除按钮改为 `disabled` + Tooltip 提示"自动维护，不可手动删除"
- 隐藏"添加股票"按钮
- 空列表文案改为"暂无数据（交易记录同步后自动更新）"

自选股成员名称同步改为 `<Link to="/stock/:code">` 可点击链接，直达 StockDetail。

---

## 九、交易统计优化（`TradeStats`）

**原问题**：胜率/胜负数按"笔"统计（同一只股票多次买卖各计一笔），与用户心智（"这只股票我是赚了还是亏了"）不符。

**变更**：
- 后端新增 `total_stocks` 字段，胜负统计重构为按股（每只股票合并所有已平仓盈亏后判胜负）
- 前端 `StatsCards` 显示文案改为 `N 只盈利 M 只亏损 / X 只股票`，同时修复涨跌幅显示：`(v * 100).toFixed(2)` → `v.toFixed(2)`（后端已返回百分比值，前端无需再乘 100）

---

## 十、API 变更汇总

| 路径 | 变更内容 |
|---|---|
| `POST /api/screen` | `strategy_params` 新增 `sell_ma_death_cross` / `sell_break_ma20` / `sell_rsi_overbought` / `sell_high_volume_drop`；`ma_cross` / `ma_cross2` 支持 `first_day` 参数 |
| `GET /api/stock/kline` | `sp` 支持 `break_ma_period` / `hvd_ma_period` / `hvd_volume_lookback` / `hvd_volume_mult`；返回 `KlineBar` 新增 `break_ma_ok` / `high_vol_drop_ok` |
| `GET /api/groups` | 需登录，按 `user_id` 隔离 |
| `POST /api/groups` | 需登录；新增保留名 / 重名校验 |
| `DELETE /api/groups/{group_id}` | 需登录；按 `user_id` 限定 |
| `GET /api/groups/{group_id}/members` | 需登录（原匿名） |
| `GET /api/trades/stats` | 响应新增 `total_stocks` 字段；`wins` / `losses` 语义改为按股统计 |

---

## 十一、已知限制

- `sell_ma_death_cross` 和 `sell_rsi_overbought` 是"近 N 日内发生过"型时点判定，未提供对应逐日 K 线图信号（K 线图上无法逐根高亮这两个卖点）
- 4 个卖点策略不在预计算表 `stock_indicator` 中，始终走现算路径
- `first_day=true` 模式强制跳过预计算快路径，全市场现算，响应延迟高于默认模式（与其他需要现算的策略一致）
- 持仓/清仓分组同步为交易写操作后的同步内联调用，不支持历史交易导入后的自动补建（下次有新交易写入时才触发）
- 管理后台全局分组（`user_id IS NULL`）与访客分组分属两套代码路径（异步 `repositories/groups.py` vs 同步 `repositories/sync_data.py`），未做统一

---

## 十二、部署步骤

```bash
# 1. 重建后端/前端镜像（含新 migration 文件）
docker compose up -d --build api worker beat

# 2. 执行数据库迁移（新增 0014）
docker compose exec -T api alembic upgrade head

# 3. 重建前端镜像
docker compose up -d --build frontend
```

无需人工数据回填。已有访客账号将在下次产生交易写操作时自动触发持仓/清仓分组同步。

---

## 十三、验证记录

- 容器内执行 `alembic upgrade head`，`\d stock_groups` 确认 `user_id` 列、`ix_stock_groups_user_id` 索引、`uq_stock_groups_user_name` 复合约束均已生效
- 铸造测试 JWT，完整链路验证：买入建仓 → 自动创建「持仓」分组并入组 → 清仓卖出 → 移入「清仓」、「持仓」清空 → 手动创建同名保留分组被拦截（400） → 跨账号数据隔离（另一账号无法看到该分组）
- 4 个卖点策略通过 `POST /api/screen` 端到端验证，参数越界触发白名单截断
- `tsc -b && vite build` 前端编译通过
- 测试数据已清理
