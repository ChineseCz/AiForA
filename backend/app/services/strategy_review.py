"""Daily strategy snapshots and rule-based forward performance review."""
from collections import defaultdict
from datetime import date
import statistics
from collections.abc import Callable
import time
import math
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import sync_data as db
from app.services import screening
from app.services import indicators

STRATEGIES = tuple(screening._PRESET_STRATEGIES)
HORIZONS = (1, 3, 5, 10, 20)
BUY_STRATEGIES = ("ma_cross", "ma_cross2", "golden_cross", "volume_breakout", "boll_breakout", "rsi_oversold_bounce")
SELL_STRATEGIES = ("sell_ma_death_cross", "sell_break_ma20", "sell_rsi_overbought", "sell_high_volume_drop")


def _is_st_name(name: object) -> bool:
    if not name:
        return False
    return "ST" in str(name).replace(" ", "").replace("　", "").upper()


def _select_entry_candidates(candidates: list[dict], *, exclude_chinext: bool = False,
                             exclude_star: bool = False, exclude_st: bool = False,
                             min_change_pct: float | None = None,
                             max_change_pct: float | None = None,
                             min_total_mv: float | None = None,
                             max_total_mv: float | None = None) -> list[dict]:
    selected = list(candidates)
    if exclude_chinext:
        selected = [s for s in selected if not s["code"].startswith(("300", "301"))]
    if exclude_star:
        selected = [s for s in selected if not s["code"].startswith(("688", "689"))]
    if exclude_st:
        selected = [s for s in selected if not _is_st_name(s.get("bar", {}).get("name"))]
    if min_change_pct is not None:
        selected = [s for s in selected if s["bar"].get("change_pct") is not None and float(s["bar"]["change_pct"]) >= min_change_pct]
    if max_change_pct is not None:
        selected = [s for s in selected if s["bar"].get("change_pct") is not None and float(s["bar"]["change_pct"]) <= max_change_pct]
    if min_total_mv is not None:
        selected = [s for s in selected if s["bar"].get("total_mv") is not None and float(s["bar"]["total_mv"]) >= min_total_mv]
    if max_total_mv is not None:
        selected = [s for s in selected if s["bar"].get("total_mv") is not None and float(s["bar"]["total_mv"]) <= max_total_mv]
    return selected


def _is_locked_limit_up(code: str, bar: dict) -> bool:
    """Whether the bar is a full-day locked upper-limit bar."""
    values = [bar.get(k) for k in ("open", "high", "low", "close")]
    if any(v is None or float(v) <= 0 for v in values):
        return False
    open_, high, low, close = (float(v) for v in values)
    if not (open_ == high == low == close):
        return False
    change = bar.get("change_pct")
    if change is None:
        return False
    limit = 20.0 if code.startswith(("300", "301", "688", "689")) else 30.0 if code.startswith(("8", "4")) else 10.0
    if _is_st_name(bar.get("name")):
        limit = 5.0
    return float(change) >= limit - 0.6


def _execution_open(code: str, bar: dict) -> float | None:
    value = bar.get("open")
    if value is None or float(value) <= 0 or _is_locked_limit_up(code, bar):
        return None
    return float(value)


def _combine_series(series: list[list[bool]], operator: str) -> list[bool]:
    if not series:
        return []
    return [all(values) if operator == "AND" else any(values) for values in zip(*series)]


def _signal_series(bars: list[dict], key: str) -> list[bool]:
    if key in ("ma_cross", "ma_cross2"):
        strict, loose = indicators.daily_signal_series(bars)
        return strict if key == "ma_cross" else loose
    if key == "golden_cross":
        closes = [b["close"] for b in bars]
        dif, dea, _ = indicators.compute_macd(closes)
        k, d, _ = indicators.compute_kdj(bars)
        return indicators.daily_golden_signal_series(dif, dea, k, d)
    if key == "volume_breakout":
        return indicators.daily_volume_breakout_series(bars)
    if key == "boll_breakout":
        return indicators.daily_boll_breakout_series(bars)
    if key == "rsi_oversold_bounce":
        return indicators.daily_rsi_bounce_series(bars)
    if key == "sell_ma_death_cross":
        closes = [b["close"] for b in bars]
        ma5 = indicators.moving_avg(closes, 5)
        ma10 = indicators.moving_avg(closes, 10)
        dif, dea, _ = indicators.compute_macd(closes)
        mid, _ = indicators.daily_sell_signal_series(closes, ma5, ma10, dif, dea)
        return mid
    if key == "sell_break_ma20":
        return indicators.daily_break_ma_series(bars)
    if key == "sell_rsi_overbought":
        return indicators.daily_rsi_overbought_series(bars)
    if key == "sell_high_volume_drop":
        return indicators.daily_high_volume_drop_series(bars)
    raise ValueError(f"不支持的组合策略：{key}")


def capture_daily(trade_date: str | None = None) -> dict:
    d = trade_date or db.get_latest_trade_date()
    if not d:
        return {"trade_date": None, "strategies": 0, "picks": 0}
    results = {}
    for key in STRATEGIES:
        rows = screening._PRESET_STRATEGIES[key](100000, None)
        results[key] = ({}, rows)
    count = db.save_strategy_daily_runs(d, results)
    return {"trade_date": d, "strategies": len(results), "picks": count}


async def run_combination(session: AsyncSession, buy_strategy: str, sell_strategy: str,
                          start: str | None = None, end: str | None = None, limit: int = 500) -> dict:
    if buy_strategy not in BUY_STRATEGIES or sell_strategy not in SELL_STRATEGIES:
        raise ValueError("买入策略或卖出策略不支持组合回测")
    if not start:
        today = date.today()
        start = date(today.year - 2, today.month, today.day).isoformat()
    clauses = ["trade_date >= :start"]
    params = {"start": start}
    if end:
        clauses.append("trade_date <= :end")
        params["end"] = end
    rows = (await session.execute(text(
        f"""
        SELECT sd.code,
               COALESCE(NULLIF(sd.name, ''), latest_names.name) AS name,
               sd.trade_date, sd.open, sd.high, sd.low, sd.close, sd.volume
        FROM stock_daily sd
        LEFT JOIN (
            SELECT DISTINCT ON (code) code, btrim(name) AS name
            FROM stock_daily
            WHERE name IS NOT NULL
              AND btrim(name) <> ''
              AND btrim(name) <> code
              AND btrim(name) !~ '^[0-9]+$'
            ORDER BY code, trade_date DESC
        ) latest_names ON latest_names.code = sd.code
        WHERE {' AND '.join(clauses)}
        ORDER BY sd.code, sd.trade_date
        """
    ), params)).mappings().all()
    by_code = defaultdict(list)
    for row in rows:
        if row["close"] and row["close"] > 0 and row["open"] is not None and row["volume"] is not None:
            by_code[row["code"]].append(dict(row))
    trades = []
    for code, bars in by_code.items():
        buy = _signal_series(bars, buy_strategy)
        sell = _signal_series(bars, sell_strategy)
        holding = None
        for i, bar in enumerate(bars):
            if holding is None and buy[i]:
                holding = (i, bar)
            elif holding is not None and i > holding[0] and sell[i]:
                entry_i, entry = holding
                trades.append({"code": code, "name": entry.get("name") or code, "buy_date": str(entry["trade_date"]),
                               "sell_date": str(bar["trade_date"]), "entry_close": float(entry["close"]),
                               "exit_close": float(bar["close"]), "holding_days": i - entry_i,
                               "return_pct": round((float(bar["close"]) / float(entry["close"]) - 1) * 100, 2), "status": "closed"})
                holding = None
        if holding is not None and len(bars) - 1 > holding[0]:
            entry_i, entry = holding
            last = bars[-1]
            trades.append({"code": code, "name": entry.get("name") or code, "buy_date": str(entry["trade_date"]),
                           "sell_date": None, "entry_close": float(entry["close"]), "exit_close": float(last["close"]),
                           "holding_days": len(bars) - 1 - entry_i,
                           "return_pct": round((float(last["close"]) / float(entry["close"]) - 1) * 100, 2), "status": "open"})
    trades.sort(key=lambda x: x["buy_date"], reverse=True)
    closed = [t for t in trades if t["status"] == "closed"]
    return {"buy_strategy": buy_strategy, "sell_strategy": sell_strategy, "start": start, "end": end,
            "trades": trades[:max(1, min(limit, 1000))],
            "summary": {"total_trades": len(trades), "closed_trades": len(closed),
                         "win_rate": round(sum(t["return_pct"] > 0 for t in closed) / len(closed) * 100, 1) if closed else None,
                         "avg_return_pct": round(statistics.mean(t["return_pct"] for t in closed), 2) if closed else None}}


async def run_expression_combination(session: AsyncSession, buy_strategies: list[str], sell_strategies: list[str],
                                     buy_operator: str = "OR", sell_operator: str = "OR",
                                     start: str | None = None, end: str | None = None, limit: int = 500,
                                     initial_capital: float = 100000, max_positions: int = 10,
                                     ranking: str = "change_pct", buy_fee_rate: float = 0.0003,
                                     sell_fee_rate: float = 0.0003, stamp_duty_rate: float = 0.0005,
                                     exclude_chinext: bool = False, exclude_star: bool = False,
                                     exclude_st: bool = True,
                                     min_change_pct: float | None = None, max_change_pct: float | None = None,
                                     min_total_mv: float | None = None, max_total_mv: float | None = None,
                                     take_profit_1_pct: float = 10, take_profit_1_fraction: float = 0.25,
                                     take_profit_2_pct: float = 20, take_profit_2_fraction: float = 0.25,
                                     take_profit_3_pct: float = 30, take_profit_3_fraction: float = 0.25,
                                     allow_second_entry: bool = True, second_entry_drawdown_pct: float = 8.0,
                                     progress_callback: Callable[[int, int], None] | None = None) -> dict:
    buy_strategies = list(dict.fromkeys(k for k in buy_strategies if k in BUY_STRATEGIES))
    sell_strategies = list(dict.fromkeys(k for k in sell_strategies if k in SELL_STRATEGIES))
    if not buy_strategies or not sell_strategies or buy_operator not in ("AND", "OR") or sell_operator not in ("AND", "OR"):
        raise ValueError("请至少选择一个买入策略和一个卖出策略，并选择 AND/OR")
    if not start:
        today = date.today(); start = date(today.year - 2, today.month, today.day).isoformat()
    # 指标需要前置历史，不能从回测起始日才开始取数据，否则起始阶段的信号会失真。
    from datetime import timedelta
    history_start = (date.fromisoformat(start) - timedelta(days=420)).isoformat()
    clauses = ["trade_date >= :start"]; params = {"start": history_start}
    if end:
        clauses.append("trade_date <= :end"); params["end"] = end
    query = text(
        f"""
        SELECT sd.code,
               COALESCE(NULLIF(sd.name, ''), sd.code) AS name,
               sd.trade_date, sd.open, sd.high, sd.low, sd.close, sd.volume,
               sd.change_pct, sd.amount, sd.total_mv
        FROM stock_daily sd
        WHERE {' AND '.join(clauses)}
        ORDER BY sd.code, sd.trade_date
        """
    )
    trades = []
    signals_by_date: dict[str, list[dict]] = defaultdict(list)
    # 组合估值只需要收盘价，不保留整行行情，显著降低内存占用。
    prices_by_date: dict[str, dict[str, float]] = defaultdict(dict)

    def process_code(code: str, bars: list[dict]) -> None:
        buy = _combine_series([_signal_series(bars, key) for key in buy_strategies], buy_operator)
        sell = _combine_series([_signal_series(bars, key) for key in sell_strategies], sell_operator)
        holding = None
        for i, bar in enumerate(bars):
            day = str(bar["trade_date"])
            if day >= start and (not end or day <= end):
                prices_by_date[day][code] = float(bar["close"])
                # 信号在收盘前确认，按当日收盘价计入执行；锁死涨停由执行层跳过。
                signals_by_date[day].append({
                    "code": code, "bar": bar, "execution_bar": bar,
                    "signal_date": day, "buy": buy[i], "sell": sell[i],
                })
            if holding is None and buy[i] and not _is_locked_limit_up(code, bar):
                holding = (i, bar)
            elif holding is not None and i > holding[0] and sell[i]:
                entry_i, entry = holding
                signal_date = str(entry["trade_date"])
                buy_date = signal_date
                trades.append({"code": code, "name": entry.get("name") or code, "signal_date": signal_date, "buy_date": buy_date, "sell_date": str(bar["trade_date"]),
                               "entry_close": float(entry["close"]), "exit_close": float(bar["close"]), "holding_days": i - entry_i,
                               "return_pct": round((float(bar["close"]) / float(entry["close"]) - 1) * 100, 2), "status": "closed"})
                holding = None
        if holding is not None and len(bars) - 1 > holding[0]:
            entry_i, entry = holding; last = bars[-1]
            signal_date = str(entry["trade_date"])
            buy_date = signal_date
            trades.append({"code": code, "name": entry.get("name") or code, "signal_date": signal_date, "buy_date": buy_date, "sell_date": None,
                           "entry_close": float(entry["close"]), "exit_close": float(last["close"]), "holding_days": len(bars) - 1 - entry_i,
                           "return_pct": round((float(last["close"]) / float(entry["close"]) - 1) * 100, 2), "status": "open"})

    # 查询结果按 code、日期排序，逐只股票流式计算；内存中最多保留一只股票的历史K线。
    result = await session.stream(query, params)
    current_code: str | None = None
    current_bars: list[dict] = []
    processed_codes = 0
    total_codes = 0
    if progress_callback:
        total_codes = int((await session.execute(text(
            "SELECT COUNT(DISTINCT code) FROM stock_daily WHERE trade_date >= :start"
            + (" AND trade_date <= :end" if end else "")),
            {"start": history_start, **({"end": end} if end else {})})).scalar_one() or 0)

    def finish_code() -> None:
        nonlocal processed_codes, current_bars
        if current_code is not None and current_bars:
            process_code(current_code, current_bars)
            processed_codes += 1
            if progress_callback and (processed_codes == 1 or processed_codes % 25 == 0 or processed_codes == total_codes):
                progress_callback(processed_codes, total_codes)
        current_bars = []

    async for raw in result.mappings():
        row = dict(raw)
        code = row["code"]
        if current_code is not None and code != current_code:
            finish_code()
        current_code = code
        if row["close"] and row["close"] > 0 and row["open"] is not None and row["volume"] is not None:
            current_bars.append(row)
    finish_code()
    trades.sort(key=lambda x: x["buy_date"], reverse=True)
    closed = [t for t in trades if t["status"] == "closed"]
    # 组合层：仍按逐股票信号驱动，但增加资金、持仓上限、排序和费用约束。
    initial_capital = max(1000.0, float(initial_capital or 100000))
    max_positions = max(1, min(int(max_positions or 10), 100))
    allow_second_entry = bool(allow_second_entry)
    second_entry_drawdown_pct = max(0.0, min(float(second_entry_drawdown_pct or 8.0), 50.0))
    ranking = ranking if ranking in ("change_pct_desc", "change_pct_asc", "amount", "code") else "change_pct_desc"
    buy_fee_rate = max(0.0, min(float(buy_fee_rate or 0), 0.02))
    sell_fee_rate = max(0.0, min(float(sell_fee_rate or 0), 0.02))
    stamp_duty_rate = max(0.0, min(float(stamp_duty_rate or 0), 0.02))
    min_change_pct = float(min_change_pct) if min_change_pct is not None else None
    max_change_pct = float(max_change_pct) if max_change_pct is not None else None
    min_total_mv = float(min_total_mv) if min_total_mv is not None else None
    max_total_mv = float(max_total_mv) if max_total_mv is not None else None
    if min_total_mv is not None and max_total_mv is not None and min_total_mv > max_total_mv:
        raise ValueError("最小市值不能大于最大市值")
    if min_change_pct is not None and max_change_pct is not None and min_change_pct > max_change_pct:
        raise ValueError("最低涨幅不能大于最高涨幅")
    take_profit_levels = tuple(sorted((
        (max(0.0, float(take_profit_1_pct)), max(0.0, min(1.0, float(take_profit_1_fraction)))),
        (max(0.0, float(take_profit_2_pct)), max(0.0, min(1.0, float(take_profit_2_fraction)))),
        (max(0.0, float(take_profit_3_pct)), max(0.0, min(1.0, float(take_profit_3_fraction)))),
    )))
    cash = initial_capital
    positions: dict[str, dict] = {}
    portfolio_trades = []
    equity_curve = []
    for day in sorted(signals_by_date):
        day_signals = signals_by_date[day]
        # 先卖出，释放资金后再处理当日买入信号。
        for signal in day_signals:
            code = signal["code"]
            pos = positions.get(code)
            if not pos:
                continue
            price = signal["execution_bar"].get("close")
            price = float(price) if price is not None and float(price) > 0 else None
            if price is None:
                continue
            if signal["sell"]:
                sell_shares = pos["shares"]
                reason = "sell_signal"
            else:
                profit_pct = (price / pos["entry_close"] - 1) * 100
                sell_shares = 0
                reason = "take_profit"
                for level, fraction in take_profit_levels:
                    if profit_pct >= level and level not in pos["take_profit_levels"]:
                        sell_shares += math.floor(pos["initial_shares"] * fraction / 100) * 100
                        pos["take_profit_levels"].add(level)
                sell_shares = min(sell_shares, pos["shares"])
            if sell_shares <= 0:
                continue
            cost_basis = pos["cost"] * sell_shares / pos["shares"]
            gross = sell_shares * price
            net = gross * (1 - sell_fee_rate - stamp_duty_rate)
            cash += net
            pos["shares"] -= sell_shares
            pos["cost"] -= cost_basis
            portfolio_trades.append({"code": code, "name": pos["name"], "signal_date": pos["signal_date"], "buy_date": pos["buy_date"], "sell_date": day,
                                     "entry_close": pos["entry_close"], "exit_close": price, "holding_days": pos["holding_days"],
                                     "return_pct": round((net / cost_basis - 1) * 100, 2),
                                     "status": "closed" if pos["shares"] == 0 else "partial",
                                     "sell_reason": reason, "shares": sell_shares})
            if pos["shares"] == 0:
                positions.pop(code, None)
        candidates = _select_entry_candidates(
            [s for s in day_signals if s["buy"] and (s["code"] not in positions or (
                allow_second_entry and not positions[s["code"]].get("second_entry_done") and
                float(s["bar"].get("close") or 0) <= positions[s["code"]]["entry_close"] * (1 - second_entry_drawdown_pct / 100)
            ))],
            exclude_chinext=exclude_chinext, exclude_star=exclude_star, exclude_st=exclude_st,
            min_change_pct=min_change_pct, max_change_pct=max_change_pct,
            min_total_mv=min_total_mv, max_total_mv=max_total_mv,
        )
        # 只过滤新开仓候选；已有持仓仍必须允许卖出，避免筛选条件变化后无法清仓。
        if ranking == "amount":
            candidates.sort(key=lambda s: float(s["bar"].get("amount") or 0), reverse=True)
        elif ranking == "code":
            candidates.sort(key=lambda s: s["code"])
        elif ranking == "change_pct_asc":
            candidates.sort(key=lambda s: float(s["bar"].get("change_pct") if s["bar"].get("change_pct") is not None else float("inf")))
        else:
            candidates.sort(key=lambda s: float(s["bar"].get("change_pct") if s["bar"].get("change_pct") is not None else float("-inf")), reverse=True)
        for signal in candidates:
            if len(positions) >= max_positions or cash <= 0:
                break
            execution_bar = signal["execution_bar"]
            # 信号日收盘前已确认，按收盘价成交；一字涨停等无法成交的标的跳过。
            price = None if _is_locked_limit_up(signal["code"], execution_bar) else execution_bar.get("close")
            price = float(price) if price is not None and float(price) > 0 else None
            if price is None:
                continue
            existing = positions.get(signal["code"])
            target = min(cash, initial_capital / max_positions)
            shares = math.floor(target * (1 - buy_fee_rate) / price / 100) * 100
            if shares <= 0:
                continue
            cost = shares * price / (1 - buy_fee_rate)
            if cost > cash:
                continue
            cash -= cost
            if existing:
                total_shares = existing["shares"] + shares
                existing["entry_close"] = (existing["cost"] + cost) / total_shares
                existing["shares"] = total_shares
                existing["cost"] += cost
                existing["second_entry_done"] = True
            else:
                positions[signal["code"]] = {"shares": shares, "initial_shares": shares, "cost": cost, "entry_close": price, "signal_date": signal["signal_date"], "buy_date": day,
                                             "name": signal["bar"].get("name") or signal["code"], "holding_days": 0,
                                             "take_profit_levels": set(), "second_entry_done": False}
        market_value = 0.0
        for code, pos in positions.items():
            current = prices_by_date[day].get(code)
            if current is not None:
                market_value += pos["shares"] * current
                pos["holding_days"] += 1
        equity_curve.append({"trade_date": day, "equity": round(cash + market_value, 2), "cash": round(cash, 2), "positions": len(positions)})
    last_equity = equity_curve[-1]["equity"] if equity_curve else initial_capital
    for code, pos in positions.items():
        last = prices_by_date[equity_curve[-1]["trade_date"]].get(code) if equity_curve else None
        if last is not None:
            price = last
            portfolio_trades.append({"code": code, "name": pos["name"], "signal_date": pos["signal_date"], "buy_date": pos["buy_date"], "sell_date": None,
                                     "entry_close": pos["entry_close"], "exit_close": price, "holding_days": pos["holding_days"],
                                     "return_pct": round((price / pos["entry_close"] - 1) * 100, 2), "status": "open",
                                     "shares": pos["shares"], "sell_reason": "end_of_period"})
    portfolio_returns = [x["equity"] / initial_capital - 1 for x in equity_curve]
    peak = initial_capital
    max_drawdown = 0.0
    for x in equity_curve:
        peak = max(peak, x["equity"])
        max_drawdown = min(max_drawdown, x["equity"] / peak - 1)
    closed_portfolio = [t for t in portfolio_trades if t["status"] == "closed"]
    return {"buy_strategies": buy_strategies, "sell_strategies": sell_strategies, "buy_operator": buy_operator, "sell_operator": sell_operator,
            "start": start, "end": end, "trades": trades[:max(1, min(limit, 1000))],
            "portfolio_trades": portfolio_trades[:max(1, min(limit, 1000))], "equity_curve": equity_curve[-500:],
            "execution": {"initial_capital": initial_capital, "max_positions": max_positions, "ranking": ranking,
                          "take_profit_levels": [{"profit_pct": p, "sell_fraction": f} for p, f in take_profit_levels],
                          "buy_fee_rate": buy_fee_rate, "sell_fee_rate": sell_fee_rate, "stamp_duty_rate": stamp_duty_rate,
                          "execution_rule": "信号日收盘价成交；一字涨停等锁死涨停无法成交并跳过",
                          "exclude_chinext": exclude_chinext, "exclude_star": exclude_star, "exclude_st": exclude_st,
                          "min_change_pct": min_change_pct, "max_change_pct": max_change_pct,
                          "min_total_mv": min_total_mv, "max_total_mv": max_total_mv,
                          "allow_second_entry": allow_second_entry, "second_entry_drawdown_pct": second_entry_drawdown_pct},
            "summary": {"total_trades": len(trades), "closed_trades": len(closed), "win_rate": round(sum(t["return_pct"] > 0 for t in closed) / len(closed) * 100, 1) if closed else None,
                         "avg_return_pct": round(statistics.mean(t["return_pct"] for t in closed), 2) if closed else None,
                         "portfolio_trades": len(portfolio_trades), "portfolio_closed_trades": len(closed_portfolio),
                         "portfolio_return_pct": round((last_equity / initial_capital - 1) * 100, 2),
                         "portfolio_max_drawdown_pct": round(max_drawdown * 100, 2),
                         "portfolio_win_rate": round(sum(t["return_pct"] > 0 for t in closed_portfolio) / len(closed_portfolio) * 100, 1) if closed_portfolio else None}}


async def list_saved_combinations(session: AsyncSession, user_id: str) -> list[dict]:
    rows = (await session.execute(text("SELECT id, name, buy_expression, sell_expression, created_at, updated_at FROM saved_strategy_combinations WHERE user_id=:u ORDER BY updated_at DESC"), {"u": user_id})).mappings().all()
    return [dict(r) for r in rows]


async def save_combination(session: AsyncSession, user_id: str, name: str, buy_expression: dict, sell_expression: dict) -> dict:
    name = name.strip()[:80]
    if not name:
        raise ValueError("组合策略名称不能为空")
    now = int(time.time())
    row = (await session.execute(text("""INSERT INTO saved_strategy_combinations (user_id, name, buy_expression, sell_expression, created_at, updated_at)
        VALUES (:u, :n, CAST(:b AS json), CAST(:s AS json), :t, :t) RETURNING id, name, buy_expression, sell_expression, created_at, updated_at"""),
        {"u": user_id, "n": name, "b": __import__("json").dumps(buy_expression, ensure_ascii=False), "s": __import__("json").dumps(sell_expression, ensure_ascii=False), "t": now})).mappings().one()
    await session.commit()
    return dict(row)

async def update_combination(session: AsyncSession, user_id: str, combination_id: int, name: str, buy_expression: dict, sell_expression: dict) -> dict:
    now = int(time.time())
    row = (await session.execute(text("""UPDATE saved_strategy_combinations
        SET name=:n, buy_expression=CAST(:b AS json), sell_expression=CAST(:s AS json), updated_at=:t
        WHERE id=:id AND user_id=:u RETURNING id, name, buy_expression, sell_expression, created_at, updated_at"""),
        {"id": combination_id, "u": user_id, "n": name.strip()[:80], "b": json.dumps(buy_expression, ensure_ascii=False), "s": json.dumps(sell_expression, ensure_ascii=False), "t": now})).mappings().first()
    if not row:
        raise ValueError("组合不存在")
    await session.commit()
    return dict(row)


async def delete_combination(session: AsyncSession, user_id: str, combination_id: int) -> bool:
    result = await session.execute(text("DELETE FROM saved_strategy_combinations WHERE id=:id AND user_id=:u"), {"id": combination_id, "u": user_id})
    await session.commit()
    return result.rowcount > 0


async def get_review(session: AsyncSession, start: str | None = None, end: str | None = None,
                     strategy: str | None = None, limit: int = 100) -> dict:
    clauses = ["1=1"]
    params: dict = {"limit": max(1, min(limit, 500))}
    if start:
        clauses.append("r.trade_date >= :start"); params["start"] = start
    if end:
        clauses.append("r.trade_date <= :end"); params["end"] = end
    if strategy and strategy in STRATEGIES:
        clauses.append("r.strategy_key = :strategy"); params["strategy"] = strategy
    rows = (await session.execute(text(f"""
        SELECT r.id, r.trade_date, r.strategy_key, r.strategy_params, r.pick_count,
               p.code, COALESCE(NULLIF(p.name, ''), latest_names.name) AS name, p.entry_close
        FROM strategy_daily_runs r JOIN strategy_daily_picks p ON p.run_id = r.id
        LEFT JOIN (
            SELECT DISTINCT ON (code) code, name
            FROM stock_daily
            WHERE name IS NOT NULL AND name <> ''
            ORDER BY code, trade_date DESC
        ) latest_names ON latest_names.code = p.code
        WHERE {' AND '.join(clauses)} ORDER BY r.trade_date DESC, r.strategy_key, p.code
    """), params)).mappings().all()
    if not rows:
        return {"items": [], "summary": [], "daily_summary": [], "strategies": list(STRATEGIES), "horizons": list(HORIZONS), "buy_strategies": list(BUY_STRATEGIES), "sell_strategies": list(SELL_STRATEGIES)}
    codes = {r["code"] for r in rows}
    history = (await session.execute(text("""
        SELECT code, trade_date, close FROM stock_daily
        WHERE code = ANY(:codes) ORDER BY code, trade_date
    """), {"codes": list(codes)})).mappings().all()
    series = defaultdict(list)
    for h in history:
        if h["close"] is not None and h["close"] > 0:
            series[h["code"]].append((str(h["trade_date"]), float(h["close"])))
    grouped = defaultdict(list)
    daily_grouped = defaultdict(list)
    items = []
    for r in rows:
        bars = series[r["code"]]
        after = [x for x in bars if x[0] > str(r["trade_date"])]
        entry = float(r["entry_close"] or 0)
        returns = {}
        for n in HORIZONS:
            returns[str(n)] = round((after[n - 1][1] / entry - 1) * 100, 2) if entry and len(after) >= n else None
        path = [x[1] / entry - 1 for x in after[:20]] if entry else []
        item = {"trade_date": str(r["trade_date"]), "strategy_key": r["strategy_key"], "strategy_params": r["strategy_params"],
                "code": r["code"], "name": r["name"] or r["code"], "entry_close": entry, "returns": returns,
                "max_gain": round(max(path) * 100, 2) if path else None,
                "max_drawdown": round(min(path) * 100, 2) if path else None}
        items.append(item); grouped[r["strategy_key"]].append(item)
        daily_grouped[(item["trade_date"], item["strategy_key"])].append(item)
    summary = []
    for key, vals in grouped.items():
        result = {"strategy_key": key, "pick_count": len(vals)}
        for n in HORIZONS:
            known = [v["returns"][str(n)] for v in vals if v["returns"][str(n)] is not None]
            result[f"d{n}_avg"] = round(statistics.mean(known), 2) if known else None
            result[f"d{n}_win_rate"] = round(sum(v > 0 for v in known) / len(known) * 100, 1) if known else None
        summary.append(result)
    summary.sort(key=lambda x: x.get("d5_avg") if x.get("d5_avg") is not None else -999, reverse=True)
    daily_summary = []
    for (trade_date, strategy_key), vals in daily_grouped.items():
        known = [v["returns"]["5"] for v in vals if v["returns"]["5"] is not None]
        daily_summary.append({"trade_date": trade_date, "strategy_key": strategy_key, "pick_count": len(vals),
                              "d5_avg": round(statistics.mean(known), 2) if known else None,
                              "d5_win_rate": round(sum(v > 0 for v in known) / len(known) * 100, 1) if known else None})
    daily_summary.sort(key=lambda x: (x["trade_date"], x["strategy_key"]), reverse=True)
    return {"items": items[:params["limit"]], "summary": summary, "daily_summary": daily_summary,
            "strategies": list(STRATEGIES), "horizons": list(HORIZONS), "buy_strategies": list(BUY_STRATEGIES), "sell_strategies": list(SELL_STRATEGIES)}
