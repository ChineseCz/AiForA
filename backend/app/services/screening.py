"""选股筛选：从旧 stock.py 移植。数据访问改走 repositories.sync_data（同步，跑在 threadpool）。

与旧实现的唯一差异：build_where 产出命名占位符（:p0/:p1）以适配 SQLAlchemy text()，
并把 SQLite 专用的 '==' 映射成 Postgres 的 '='（其余操作符 Postgres 原生支持，含 '!='）。
"""
from datetime import date, timedelta

from app.repositories import sync_data as db


class InsufficientHistoryError(ValueError):
    """历史K线数据不足，无法计算均线类预设策略。"""


class InsufficientFinanceError(ValueError):
    """财务指标数据不足，无法计算基本面类预设策略。"""


FIELD_WHITELIST = {
    "close": "close",
    "change_pct": "change_pct",
    "volume": "volume",
    "amount": "amount",
    "turnover_rate": "turnover_rate",
    "pe_ttm": "pe_ttm",
    "pb": "pb",
    "total_mv": "total_mv",
    "circ_mv": "circ_mv",
}
OP_WHITELIST = {">", ">=", "<", "<=", "==", "!="}
# SQLite 接受 '=='，Postgres 不接受 —— 渲染 SQL 时映射。
_OP_SQL = {"==": "=", "!=": "!="}


def build_where(conditions: list[dict]) -> tuple[str, dict]:
    """结构化条件 → 参数化 SQL 片段 + 命名参数字典。字段/操作符必须在白名单内。"""
    where_sql = ""
    params: dict = {}
    for i, cond in enumerate(conditions or []):
        field = FIELD_WHITELIST.get(cond.get("field"))
        op = cond.get("op")
        if field is None or op not in OP_WHITELIST:
            raise ValueError(f"非法筛选条件: {cond}")
        try:
            value = float(cond.get("value"))
        except (TypeError, ValueError):
            raise ValueError(f"非法数值: {cond}")
        op_sql = _OP_SQL.get(op, op)
        where_sql += f" AND {field} {op_sql} :p{i}"
        params[f"p{i}"] = value
    return where_sql, params


def is_st_or_s(name: str) -> bool:
    name = name or ""
    return "ST" in name or "S" in name


def is_main_board(code: str) -> bool:
    return not (code or "").startswith(("688", "689", "300", "301"))


def is_kechuang(code: str) -> bool:
    return (code or "").startswith("688")


def _load_ma_series(candidates: set[str], since_days: int = 90) -> dict[str, list[dict]]:
    since = (date.today() - timedelta(days=since_days)).isoformat()
    hist = db.get_history_since(since)
    series: dict[str, list[dict]] = {}
    for row in hist:
        if row["code"] in candidates:
            series.setdefault(row["code"], []).append(row)
    return series


def _calendar_days_for(bars_needed: int) -> int:
    """按所需最少K线根数估算要回溯多少自然日（含节假日/周末缓冲），下限90天（原有默认窗口）。"""
    return max(90, int(bars_needed * 2.2) + 30)


def _fresh_indicators() -> dict[str, dict] | None:
    """预计算指标表若与最新行情日一致且非空，则返回其 map（快路径）；否则 None（回退现算）。"""
    ind_date = db.indicator_trade_date()
    if not ind_date or ind_date != db.get_latest_trade_date():
        return None
    ind = db.get_indicator_map()
    return ind or None


def _sorted_hits(hits: list[dict], limit: int) -> list[dict]:
    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


_MA_CROSS_DEFAULTS = {"ma_fast": 5, "ma_mid": 10, "ma_slow": 20, "cross_days": 3, "rise_days": 5, "rise_pct": 0.03, "first_day": False}
_GOLDEN_CROSS_DEFAULTS = {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9, "kdj_window": 9, "cross_days": 4, "require_both": True}
_FUND_OK_DEFAULTS = {"net_profit_yoy_min": 0.0, "eps_min": 0.1, "roe_min": 3.0, "revenue_yoy_min": 10.0, "gross_margin_min": 10.0}
_VOLUME_BREAKOUT_DEFAULTS = {"breakout_days": 20, "volume_mult": 1.5}
_PULLBACK_LOW_VOLUME_DEFAULTS = {
    "lookback_days": 10, "ma_period": 20, "near_pct": 0.02,
    "recent_days": 3, "avg_days": 20, "spike_mult": 1.5, "low_volume_mult": 0.7,
}
_BOLL_BREAKOUT_DEFAULTS = {"period": 20, "mult": 2.0, "squeeze_days": 60, "squeeze_pct": 0.3}
_RSI_BOUNCE_DEFAULTS = {"period": 14, "threshold": 30.0, "lookback_days": 2}
_TURNOVER_SURGE_DEFAULTS = {"turnover_min": 5.0, "change_pct_min": 4.0, "change_pct_max": 9.5}
_VOLUME_PRICE_UP_DEFAULTS = {"streak_days": 3}
_MA_DEATH_CROSS_DEFAULTS = {"cross_days": 3}
_BREAK_MA20_DEFAULTS = {"ma_period": 20}
_RSI_OVERBOUGHT_DEFAULTS = {"period": 14, "threshold": 70.0, "lookback_days": 2}
_HIGH_VOLUME_DROP_DEFAULTS = {"ma_period": 20, "volume_lookback": 20, "volume_mult": 1.5}

# 每个可调参数的取值范围（int: (min, max)；float: (min, max)），供 sanitize_strategy_params 校验/裁剪，
# 防止恶意/畸形请求传入超大周期把现算路径拖成 O(n·超大窗口) 的 DoS，或非数值类型导致后续计算抛异常。
_PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "ma_fast": (2, 60), "ma_mid": (2, 120), "ma_slow": (2, 250),
    "cross_days": (1, 20), "rise_days": (1, 60), "rise_pct": (-0.5, 2.0),
    "macd_fast": (2, 60), "macd_slow": (2, 120), "macd_signal": (2, 60),
    "kdj_window": (2, 60),
    "net_profit_yoy_min": (-100, 1000), "eps_min": (-100, 1000), "roe_min": (-100, 1000),
    "revenue_yoy_min": (-100, 1000), "gross_margin_min": (-100, 1000),
    "breakout_days": (2, 120), "volume_mult": (1.0, 10.0),
    "lookback_days": (1, 60), "ma_period": (2, 120), "near_pct": (0.0, 0.3),
    "recent_days": (1, 30), "avg_days": (2, 120), "spike_mult": (1.0, 10.0), "low_volume_mult": (0.1, 1.0),
    "period": (2, 120), "mult": (1.0, 4.0), "squeeze_days": (5, 250), "squeeze_pct": (0.05, 1.0),
    "threshold": (5.0, 90.0),
    "turnover_min": (0.0, 50.0), "change_pct_min": (-20.0, 20.0), "change_pct_max": (-20.0, 21.0),
    "streak_days": (2, 10),
    "volume_lookback": (2, 120),
}
_BOOL_PARAMS = {"require_both", "first_day"}


def sanitize_strategy_params(strategy_key: str, raw: dict | None, defaults: dict) -> dict:
    """按白名单键裁剪/类型转换用户传入的策略参数；未知键忽略，非法值回退默认值。"""
    if not raw:
        return {}
    out: dict = {}
    for key, default in defaults.items():
        if key not in raw:
            continue
        val = raw[key]
        if key in _BOOL_PARAMS:
            out[key] = bool(val)
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        lo, hi = _PARAM_BOUNDS.get(key, (float("-inf"), float("inf")))
        num = max(lo, min(hi, num))
        out[key] = int(num) if isinstance(default, int) else num
    return out


def screen_ma_cross(limit: int = 200, params: dict | None = None) -> list[dict]:
    from app.services import indicators
    p = {**_MA_CROSS_DEFAULTS, **sanitize_strategy_params("ma_cross", params, _MA_CROSS_DEFAULTS)}
    first_day = bool(p.get("first_day"))
    is_default = not first_day and {k: v for k, v in p.items() if k != "first_day"} == {k: v for k, v in _MA_CROSS_DEFAULTS.items() if k != "first_day"}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and is_main_board(r["code"]) and not is_st_or_s(r.get("name"))
        and r.get("volume")
    }
    if not candidates:
        return []

    if is_default:
        ind = _fresh_indicators()
        if ind is not None:  # 快路径：读预计算标志（仅默认参数可用，自定义参数走现算）
            hits = [
                dict(latest_by_code[code]) for code, f in ind.items()
                if code in candidates and f["cross1"] and f["cross23"] and f["rise5"]
                and f["price_above20"] and f["duotou"]
            ]
            return _sorted_hits(hits, limit)

    series = _load_ma_series(candidates, _calendar_days_for(max(p["ma_slow"], p["rise_days"])) + (3 if first_day else 0))
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < p["ma_slow"] + 3:
        raise InsufficientHistoryError("历史数据不足，请先运行历史K线回补")

    hits = []
    for code, bars in series.items():
        if first_day:
            strict_series, _ = indicators.daily_signal_series(
                bars, p["cross_days"], p["rise_days"], p["rise_pct"],
            )
            if len(strict_series) < 2 or not (strict_series[-1] and not strict_series[-2]):
                continue
        else:
            m = indicators.ma_cross_metrics(
                bars, p["ma_fast"], p["ma_mid"], p["ma_slow"], p["cross_days"], p["rise_days"], p["rise_pct"],
            )
            if not m or not (m["cross1_in_3days"] and m["cross23_in_3days"] and m["rise5"]):
                continue
            price_above20 = m["closes"][-1] > m["ma20"][-1]
            duotou = m["ma5"][-1] is not None and m["ma10"][-1] is not None and m["ma5"][-1] > m["ma10"][-1] > m["ma20"][-1]
            if not (price_above20 and duotou):
                continue
        hits.append(dict(latest_by_code.get(code, {"code": code})))

    return _sorted_hits(hits, limit)


def screen_ma_cross2(limit: int = 200, params: dict | None = None) -> list[dict]:
    from app.services import indicators
    p = {**_MA_CROSS_DEFAULTS, **sanitize_strategy_params("ma_cross2", params, _MA_CROSS_DEFAULTS)}
    first_day = bool(p.get("first_day"))
    is_default = not first_day and {k: v for k, v in p.items() if k != "first_day"} == {k: v for k, v in _MA_CROSS_DEFAULTS.items() if k != "first_day"}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and not is_kechuang(r["code"]) and not is_st_or_s(r.get("name"))
        and r.get("volume")
    }
    if not candidates:
        return []

    if is_default:
        ind = _fresh_indicators()
        if ind is not None:  # 快路径
            hits = [
                dict(latest_by_code[code]) for code, f in ind.items()
                if code in candidates and f["cross1"] and f["cross23"] and f["rise5"]
            ]
            return _sorted_hits(hits, limit)

    series = _load_ma_series(candidates, _calendar_days_for(max(p["ma_slow"], p["rise_days"])) + (3 if first_day else 0))
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < p["ma_slow"] + 3:
        raise InsufficientHistoryError("历史数据不足，请先运行历史K线回补")

    hits = []
    for code, bars in series.items():
        if first_day:
            _, loose_series = indicators.daily_signal_series(
                bars, p["cross_days"], p["rise_days"], p["rise_pct"],
            )
            if len(loose_series) < 2 or not (loose_series[-1] and not loose_series[-2]):
                continue
        else:
            m = indicators.ma_cross_metrics(
                bars, p["ma_fast"], p["ma_mid"], p["ma_slow"], p["cross_days"], p["rise_days"], p["rise_pct"],
            )
            if not (m and m["cross1_in_3days"] and m["cross23_in_3days"] and m["rise5"]):
                continue
        hits.append(dict(latest_by_code.get(code, {"code": code})))

    return _sorted_hits(hits, limit)


def screen_golden_cross(limit: int = 200, params: dict | None = None) -> list[dict]:
    from app.services import indicators
    p = {**_GOLDEN_CROSS_DEFAULTS, **sanitize_strategy_params("golden_cross", params, _GOLDEN_CROSS_DEFAULTS)}
    is_default = p == _GOLDEN_CROSS_DEFAULTS

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")
    }
    if not candidates:
        return []

    if is_default:
        ind = _fresh_indicators()
        if ind is not None:  # 快路径
            hits = [
                dict(latest_by_code[code]) for code, f in ind.items()
                if code in candidates and f["macd_recent"] and f["kdj_recent"]
            ]
            return _sorted_hits(hits, limit)

    min_bars = max(p["macd_slow"] + p["macd_signal"], p["kdj_window"]) + p["cross_days"]
    series = _load_ma_series(candidates, _calendar_days_for(min_bars))
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < max(23, min_bars):
        raise InsufficientHistoryError("历史数据不足，请先运行历史K线回补")

    hits = []
    for code, bars in series.items():
        m = indicators.golden_cross_metrics(
            bars, p["macd_fast"], p["macd_slow"], p["macd_signal"], p["kdj_window"], p["cross_days"],
        )
        if not m:
            continue
        ok = (m["macd_recent"] and m["kdj_recent"]) if p["require_both"] else (m["macd_recent"] or m["kdj_recent"])
        if ok:
            hits.append(dict(latest_by_code.get(code, {"code": code})))

    return _sorted_hits(hits, limit)


def screen_fund_ok(limit: int = 200, params: dict | None = None) -> list[dict]:
    p = {**_FUND_OK_DEFAULTS, **sanitize_strategy_params("fund_ok", params, _FUND_OK_DEFAULTS)}

    fin_map = db.get_finance_map()
    if not fin_map:
        raise InsufficientFinanceError("还没有财务指标数据，请先同步财报指标")

    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}

    hits = []
    for code, fin in fin_map.items():
        quote = latest_by_code.get(code)
        if not quote:
            continue
        if is_st_or_s(quote.get("name") or fin.get("name")):
            continue
        net_profit_yoy, eps, roe, revenue_yoy, gross_margin = (
            fin.get("net_profit_yoy"), fin.get("eps"), fin.get("roe"),
            fin.get("revenue_yoy"), fin.get("gross_margin"),
        )
        if None in (net_profit_yoy, eps, roe, revenue_yoy, gross_margin):
            continue
        if (
            net_profit_yoy > p["net_profit_yoy_min"] and eps > p["eps_min"] and roe > p["roe_min"]
            and revenue_yoy > p["revenue_yoy_min"] and gross_margin > p["gross_margin_min"]
        ):
            row = dict(quote)
            row.update(
                eps=eps, roe=roe, net_profit_yoy=net_profit_yoy,
                revenue_yoy=revenue_yoy, gross_margin=gross_margin, report_date=fin.get("report_date"),
            )
            hits.append(row)

    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


def screen_volume_breakout(limit: int = 200, params: dict | None = None) -> list[dict]:
    """放量突破：收盘价突破近N日最高价，且当日成交量 > N日均量 × 倍数。"""
    from app.services import indicators
    p = {**_VOLUME_BREAKOUT_DEFAULTS, **sanitize_strategy_params("volume_breakout", params, _VOLUME_BREAKOUT_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(p["breakout_days"]))
    hits = []
    for code, bars in series.items():
        m = indicators.volume_breakout_metrics(bars, p["breakout_days"], p["volume_mult"])
        if m and m["breakout"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_pullback_low_volume(limit: int = 200, params: dict | None = None) -> list[dict]:
    """缩量回踩：近期曾放量上涨，现价回踩均线附近，近期量能明显萎缩。"""
    from app.services import indicators
    p = {**_PULLBACK_LOW_VOLUME_DEFAULTS, **sanitize_strategy_params("pullback_low_volume", params, _PULLBACK_LOW_VOLUME_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    need_days = max(p["lookback_days"], p["avg_days"]) + p["recent_days"]
    series = _load_ma_series(candidates, _calendar_days_for(need_days))
    hits = []
    for code, bars in series.items():
        m = indicators.pullback_low_volume_metrics(
            bars, p["lookback_days"], p["ma_period"], p["near_pct"],
            p["recent_days"], p["avg_days"], p["spike_mult"], p["low_volume_mult"],
        )
        if m and m["had_spike_rise"] and m["near_ma"] and m["low_volume"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_boll_breakout(limit: int = 200, params: dict | None = None) -> list[dict]:
    """布林带收口突破：带宽近期处于低位（收口），今日收盘突破上轨。"""
    from app.services import indicators
    p = {**_BOLL_BREAKOUT_DEFAULTS, **sanitize_strategy_params("boll_breakout", params, _BOLL_BREAKOUT_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(p["period"] + p["squeeze_days"]))
    hits = []
    for code, bars in series.items():
        m = indicators.boll_squeeze_breakout_metrics(bars, p["period"], p["mult"], p["squeeze_days"], p["squeeze_pct"])
        if m and m["squeezed"] and m["breakout"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_rsi_oversold_bounce(limit: int = 200, params: dict | None = None) -> list[dict]:
    """RSI超卖反弹：RSI从阈值下方回升到阈值上方，且当日收阳。"""
    from app.services import indicators
    p = {**_RSI_BOUNCE_DEFAULTS, **sanitize_strategy_params("rsi_oversold_bounce", params, _RSI_BOUNCE_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(p["period"] + p["lookback_days"]))
    hits = []
    for code, bars in series.items():
        m = indicators.rsi_bounce_metrics(bars, p["period"], p["threshold"], p["lookback_days"])
        if m and m["bounced"] and m["bullish_today"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_turnover_surge(limit: int = 200, params: dict | None = None) -> list[dict]:
    """换手异动：换手率超过阈值，且涨幅在区间内（排除涨停/跌停）。只需最新快照，不用历史K线。"""
    p = {**_TURNOVER_SURGE_DEFAULTS, **sanitize_strategy_params("turnover_surge", params, _TURNOVER_SURGE_DEFAULTS)}

    latest = db.get_latest_rows()
    hits = [
        r for r in latest
        if r.get("code") and not is_st_or_s(r.get("name"))
        and r.get("turnover_rate") is not None and r.get("change_pct") is not None
        and r["turnover_rate"] > p["turnover_min"]
        and p["change_pct_min"] <= r["change_pct"] <= p["change_pct_max"]
    ]
    return _sorted_hits(hits, limit)


def screen_volume_price_up(limit: int = 200, params: dict | None = None) -> list[dict]:
    """量价齐升：连续N日成交量与收盘价同步递增。"""
    from app.services import indicators
    p = {**_VOLUME_PRICE_UP_DEFAULTS, **sanitize_strategy_params("volume_price_up", params, _VOLUME_PRICE_UP_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(p["streak_days"]))
    hits = []
    for code, bars in series.items():
        m = indicators.volume_price_up_metrics(bars, p["streak_days"])
        if m and m["streak_ok"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_sell_ma_death_cross(limit: int = 200, params: dict | None = None) -> list[dict]:
    """MA死叉卖点：近N日MA5下穿MA10。"""
    from app.services import indicators
    p = {**_MA_DEATH_CROSS_DEFAULTS, **sanitize_strategy_params("sell_ma_death_cross", params, _MA_DEATH_CROSS_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(10 + p["cross_days"]))
    hits = []
    for code, bars in series.items():
        m = indicators.ma_death_cross_metrics(bars, p["cross_days"])
        if m and m["death_cross"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_sell_break_ma20(limit: int = 200, params: dict | None = None) -> list[dict]:
    """跌破均线卖点：收盘价从均线上方穿破到下方。"""
    from app.services import indicators
    p = {**_BREAK_MA20_DEFAULTS, **sanitize_strategy_params("sell_break_ma20", params, _BREAK_MA20_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(p["ma_period"]))
    hits = []
    for code, bars in series.items():
        m = indicators.break_ma_metrics(bars, p["ma_period"])
        if m and m["broke"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_sell_rsi_overbought(limit: int = 200, params: dict | None = None) -> list[dict]:
    """RSI超买回落卖点：RSI由>阈值回落到<=阈值。"""
    from app.services import indicators
    p = {**_RSI_OVERBOUGHT_DEFAULTS, **sanitize_strategy_params("sell_rsi_overbought", params, _RSI_OVERBOUGHT_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(p["period"] + p["lookback_days"]))
    hits = []
    for code, bars in series.items():
        m = indicators.rsi_overbought_metrics(bars, p["period"], p["threshold"], p["lookback_days"])
        if m and m["fell"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


def screen_sell_high_volume_drop(limit: int = 200, params: dict | None = None) -> list[dict]:
    """高位放量阴线卖点：收盘价在均线上方 + 当日阴线 + 成交量>均量×倍数。"""
    from app.services import indicators
    p = {**_HIGH_VOLUME_DROP_DEFAULTS, **sanitize_strategy_params("sell_high_volume_drop", params, _HIGH_VOLUME_DROP_DEFAULTS)}

    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {r["code"] for r in latest if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")}
    if not candidates:
        return []

    series = _load_ma_series(candidates, _calendar_days_for(max(p["ma_period"], p["volume_lookback"])))
    hits = []
    for code, bars in series.items():
        m = indicators.high_volume_drop_metrics(bars, p["ma_period"], p["volume_lookback"], p["volume_mult"])
        if m and m["above_ma"] and m["bearish"] and m["high_vol"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))
    return _sorted_hits(hits, limit)


_PRESET_STRATEGIES = {
    "ma_cross": screen_ma_cross,
    "ma_cross2": screen_ma_cross2,
    "golden_cross": screen_golden_cross,
    "fund_ok": screen_fund_ok,
    "volume_breakout": screen_volume_breakout,
    "pullback_low_volume": screen_pullback_low_volume,
    "boll_breakout": screen_boll_breakout,
    "rsi_oversold_bounce": screen_rsi_oversold_bounce,
    "turnover_surge": screen_turnover_surge,
    "volume_price_up": screen_volume_price_up,
    "sell_ma_death_cross": screen_sell_ma_death_cross,
    "sell_break_ma20": screen_sell_break_ma20,
    "sell_rsi_overbought": screen_sell_rsi_overbought,
    "sell_high_volume_drop": screen_sell_high_volume_drop,
}


def screen_combined(strategy_keys: list[str], limit: int = 200, strategy_params: dict | None = None) -> list[dict]:
    keys = [k for k in dict.fromkeys(strategy_keys or []) if k in _PRESET_STRATEGIES]
    if not keys:
        raise ValueError("请至少选择一个预设策略")

    strategy_params = strategy_params or {}
    results = {k: _PRESET_STRATEGIES[k](100000, strategy_params.get(k)) for k in keys}

    common_codes = None
    for hits in results.values():
        codes = {r["code"] for r in hits if r.get("code")}
        common_codes = codes if common_codes is None else (common_codes & codes)
    if not common_codes:
        return []

    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    merged: dict[str, dict] = {}
    for hits in results.values():
        for r in hits:
            code = r.get("code")
            if code in common_codes:
                row = merged.setdefault(code, dict(latest_by_code.get(code, {"code": code})))
                row.update({k: v for k, v in r.items() if v is not None})

    combined_hits = list(merged.values())
    combined_hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return combined_hits[:limit]


def screen_combined_all(
    strategy_keys: list[str], conditions: list[dict], limit: int = 200, strategy_params: dict | None = None,
) -> list[dict]:
    keys = [k for k in dict.fromkeys(strategy_keys or []) if k in _PRESET_STRATEGIES]
    has_presets = bool(keys)
    has_conditions = bool(conditions)
    if not has_presets and not has_conditions:
        raise ValueError("请至少选择一个预设策略，或填写筛选条件")

    strategy_params = strategy_params or {}
    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}

    preset_rows: dict[str, dict] = {}
    if has_presets:
        results = {k: _PRESET_STRATEGIES[k](100000, strategy_params.get(k)) for k in keys}
        common = None
        for hits in results.values():
            codes = {r["code"] for r in hits if r.get("code")}
            common = codes if common is None else (common & codes)
        for hits in (results.values() if common else []):
            for r in hits:
                code = r.get("code")
                if code in common:
                    row = preset_rows.setdefault(code, {})
                    row.update({k: v for k, v in r.items() if v is not None})

    cond_rows: dict[str, dict] = {}
    if has_conditions:
        trade_date = db.get_latest_trade_date()
        where_sql, params = build_where(conditions)
        cond_rows = {
            r["code"]: r for r in db.screen_stocks(trade_date, where_sql, params, 100000) if r.get("code")
        }

    if has_presets and has_conditions:
        common_codes = set(preset_rows) & set(cond_rows)
    elif has_presets:
        common_codes = set(preset_rows)
    else:
        common_codes = set(cond_rows)
    if not common_codes:
        return []

    merged: dict[str, dict] = {}
    for code in common_codes:
        row = dict(latest_by_code.get(code, {"code": code}))
        row.update({k: v for k, v in preset_rows.get(code, {}).items() if v is not None})
        row.update({k: v for k, v in cond_rows.get(code, {}).items() if v is not None})
        merged[code] = row

    hits = list(merged.values())
    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]
