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


def _load_ma_series(candidates: set[str]) -> dict[str, list[dict]]:
    since = (date.today() - timedelta(days=90)).isoformat()
    hist = db.get_history_since(since)
    series: dict[str, list[dict]] = {}
    for row in hist:
        if row["code"] in candidates:
            series.setdefault(row["code"], []).append(row)
    return series


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


def screen_ma_cross(limit: int = 200) -> list[dict]:
    from app.services import indicators
    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and is_main_board(r["code"]) and not is_st_or_s(r.get("name"))
        and r.get("volume")
    }
    if not candidates:
        return []

    ind = _fresh_indicators()
    if ind is not None:  # 快路径：读预计算标志
        hits = [
            dict(latest_by_code[code]) for code, f in ind.items()
            if code in candidates and f["cross1"] and f["cross23"] and f["rise5"]
            and f["price_above20"] and f["duotou"]
        ]
        return _sorted_hits(hits, limit)

    series = _load_ma_series(candidates)
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < 23:
        raise InsufficientHistoryError("历史数据不足，请先运行历史K线回补")

    hits = []
    for code, bars in series.items():
        m = indicators.ma_cross_metrics(bars)
        if not m or not (m["cross1_in_3days"] and m["cross23_in_3days"] and m["rise5"]):
            continue
        price_above20 = m["closes"][-1] > m["ma20"][-1]
        duotou = m["ma5"][-1] is not None and m["ma10"][-1] is not None and m["ma5"][-1] > m["ma10"][-1] > m["ma20"][-1]
        if price_above20 and duotou:
            hits.append(dict(latest_by_code.get(code, {"code": code})))

    return _sorted_hits(hits, limit)


def screen_ma_cross2(limit: int = 200) -> list[dict]:
    from app.services import indicators
    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and not is_kechuang(r["code"]) and not is_st_or_s(r.get("name"))
        and r.get("volume")
    }
    if not candidates:
        return []

    ind = _fresh_indicators()
    if ind is not None:  # 快路径
        hits = [
            dict(latest_by_code[code]) for code, f in ind.items()
            if code in candidates and f["cross1"] and f["cross23"] and f["rise5"]
        ]
        return _sorted_hits(hits, limit)

    series = _load_ma_series(candidates)
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < 23:
        raise InsufficientHistoryError("历史数据不足，请先运行历史K线回补")

    hits = []
    for code, bars in series.items():
        m = indicators.ma_cross_metrics(bars)
        if m and m["cross1_in_3days"] and m["cross23_in_3days"] and m["rise5"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))

    return _sorted_hits(hits, limit)


def screen_golden_cross(limit: int = 200) -> list[dict]:
    from app.services import indicators
    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")
    }
    if not candidates:
        return []

    ind = _fresh_indicators()
    if ind is not None:  # 快路径
        hits = [
            dict(latest_by_code[code]) for code, f in ind.items()
            if code in candidates and f["macd_recent"] and f["kdj_recent"]
        ]
        return _sorted_hits(hits, limit)

    series = _load_ma_series(candidates)
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < 23:
        raise InsufficientHistoryError("历史数据不足，请先运行历史K线回补")

    hits = []
    for code, bars in series.items():
        m = indicators.golden_cross_metrics(bars)
        if m and m["macd_recent"] and m["kdj_recent"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))

    return _sorted_hits(hits, limit)


def screen_fund_ok(limit: int = 200) -> list[dict]:
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
        if net_profit_yoy > 0 and eps > 0.1 and roe > 3 and revenue_yoy > 10 and gross_margin > 10:
            row = dict(quote)
            row.update(
                eps=eps, roe=roe, net_profit_yoy=net_profit_yoy,
                revenue_yoy=revenue_yoy, gross_margin=gross_margin, report_date=fin.get("report_date"),
            )
            hits.append(row)

    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


_PRESET_STRATEGIES = {
    "ma_cross": screen_ma_cross,
    "ma_cross2": screen_ma_cross2,
    "golden_cross": screen_golden_cross,
    "fund_ok": screen_fund_ok,
}


def screen_combined(strategy_keys: list[str], limit: int = 200) -> list[dict]:
    keys = [k for k in dict.fromkeys(strategy_keys or []) if k in _PRESET_STRATEGIES]
    if not keys:
        raise ValueError("请至少选择一个预设策略")

    results = {k: _PRESET_STRATEGIES[k](100000) for k in keys}

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


def screen_combined_all(strategy_keys: list[str], conditions: list[dict], limit: int = 200) -> list[dict]:
    keys = [k for k in dict.fromkeys(strategy_keys or []) if k in _PRESET_STRATEGIES]
    has_presets = bool(keys)
    has_conditions = bool(conditions)
    if not has_presets and not has_conditions:
        raise ValueError("请至少选择一个预设策略，或填写筛选条件")

    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}

    preset_rows: dict[str, dict] = {}
    if has_presets:
        results = {k: _PRESET_STRATEGIES[k](100000) for k in keys}
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
