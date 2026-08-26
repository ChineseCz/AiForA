"""个股详情页视图：K线 / 基本面 / 分组成员。从旧 stock.py 移植。数据走 sync_data。"""
from datetime import date

from app.repositories import sync_data as db
from app.services import indicators, matching
from app.services.external import sina

INDEX_NAMES = {
    "sh000001": "上证指数", "sz399001": "深证成指", "sz399006": "创业板指", "sh000300": "沪深300",
}


def _aggregate_bars(bars: list[dict], period: str) -> list[dict]:
    """把日线聚合为周线/月线；trade_date 使用该周期最后一个交易日。"""
    if period == "day":
        return bars
    groups: dict[tuple[int, int], list[dict]] = {}
    for bar in bars:
        day = date.fromisoformat(bar["trade_date"])
        key = (day.isocalendar().year, day.isocalendar().week) if period == "week" else (day.year, day.month)
        groups.setdefault(key, []).append(bar)
    out: list[dict] = []
    for items in groups.values():
        items.sort(key=lambda x: x["trade_date"])
        out.append({
            "trade_date": items[-1]["trade_date"],
            "open": items[0]["open"],
            "high": max(x["high"] for x in items),
            "low": min(x["low"] for x in items),
            "close": items[-1]["close"],
            "volume": sum(x["volume"] or 0 for x in items),
        })
    return out


def get_kline_view(code: str, sp: dict | None = None, period: str = "day") -> dict:
    """日/周/月K线 + 对应周期指标和买卖信号。sp 为可选信号参数覆盖。"""
    if period not in ("day", "week", "month"):
        period = "day"
    sp = sp or {}
    bond = db.get_latest_bond_by_code(code)
    if bond:
        name = bond.get("name") or code
        bars = db.get_bond_history_for_code(code)
    else:
        name = (db.get_latest_row_by_code(code) or {}).get("name") or code
        bars = db.get_history_for_code(code)
    bars = _aggregate_bars(bars, period)
    if len(bars) < 23:
        return {"code": code, "name": name, "period": period, "bars": []}

    closes = [b["close"] for b in bars]
    ma5 = indicators.moving_avg(closes, 5)
    ma10 = indicators.moving_avg(closes, 10)
    ma20 = indicators.moving_avg(closes, 20)
    dif, dea, macd = indicators.compute_macd(closes)
    k, d, j = indicators.compute_kdj(bars)
    strict_ok, loose_ok = indicators.daily_signal_series(
        bars,
        cross_days=int(sp.get("cross_days", 3)),
        rise_days=int(sp.get("rise_days", 5)),
        rise_pct=float(sp.get("rise_pct", 0.03)),
    )
    golden_ok = indicators.daily_golden_signal_series(
        dif, dea, k, d,
        cross_days=int(sp.get("golden_cross_days", 4)),
        require_both=bool(sp.get("require_both", True)),
    )
    mid_reverse_ok, stop_loss_ok = indicators.daily_sell_signal_series(closes, ma5, ma10, dif, dea)
    vb_ok = indicators.daily_volume_breakout_series(
        bars, int(sp.get("vb_breakout_days", 20)), float(sp.get("vb_volume_mult", 1.5)),
    )
    boll_ok = indicators.daily_boll_breakout_series(
        bars, int(sp.get("boll_period", 20)), float(sp.get("boll_mult", 2.0)),
    )
    rsi_bounce_ok = indicators.daily_rsi_bounce_series(
        bars, int(sp.get("rsi_period", 14)), float(sp.get("rsi_buy_threshold", 30.0)),
    )
    rsi_ob_ok = indicators.daily_rsi_overbought_series(
        bars, int(sp.get("rsi_period", 14)), float(sp.get("rsi_sell_threshold", 70.0)),
    )
    break_ma_ok = indicators.daily_break_ma_series(
        bars, int(sp.get("break_ma_period", 20)),
    )
    hvd_ok = indicators.daily_high_volume_drop_series(
        bars,
        int(sp.get("hvd_ma_period", 20)),
        int(sp.get("hvd_volume_lookback", 20)),
        float(sp.get("hvd_volume_mult", 1.5)),
    )

    out_bars = []
    for i, b in enumerate(bars):
        out_bars.append({
            "trade_date": b["trade_date"],
            "open": b["open"] if b["open"] is not None else b["close"],
            "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"],
            "ma5": ma5[i], "ma10": ma10[i], "ma20": ma20[i],
            "dif": dif[i], "dea": dea[i], "macd": macd[i],
            "k": k[i], "d": d[i], "j": j[i],
            "strict_ok": strict_ok[i], "loose_ok": loose_ok[i], "golden_ok": golden_ok[i],
            "mid_reverse_ok": mid_reverse_ok[i], "stop_loss_ok": stop_loss_ok[i],
            "volume_breakout_ok": vb_ok[i], "boll_breakout_ok": boll_ok[i],
            "rsi_bounce_ok": rsi_bounce_ok[i], "rsi_overbought_ok": rsi_ob_ok[i],
            "break_ma_ok": break_ma_ok[i], "high_vol_drop_ok": hvd_ok[i],
        })
    return {"code": code, "name": name, "period": period, "bars": out_bars}


def get_index_kline_view(code: str, period: str = "day") -> dict:
    """大盘指数日/周/月K线 + MA/MACD/KDJ，供看板首页画图。数据不落库，实时从新浪拉取。

    只返回历史 bars，不做实时合并——实时报价由前端通过 /api/stock/quote 单独轮询后在前端合并，
    与个股详情页保持一致的模式。
    """
    if period not in ("day", "week", "month"):
        period = "day"
    name = INDEX_NAMES.get(code, code)
    bars = sina.fetch_index_kline(code)
    bars = _aggregate_bars(bars, period)
    if len(bars) < 23:
        return {"code": code, "name": name, "period": period, "bars": []}

    closes = [b["close"] for b in bars]
    ma5 = indicators.moving_avg(closes, 5)
    ma10 = indicators.moving_avg(closes, 10)
    ma20 = indicators.moving_avg(closes, 20)
    dif, dea, macd = indicators.compute_macd(closes)
    k, d, j = indicators.compute_kdj(bars)
    strict_ok, loose_ok = indicators.daily_signal_series(bars)
    golden_ok = indicators.daily_golden_signal_series(dif, dea, k, d)
    mid_reverse_ok, stop_loss_ok = indicators.daily_sell_signal_series(closes, ma5, ma10, dif, dea)

    out_bars = []
    for i, b in enumerate(bars):
        out_bars.append({
            "trade_date": b["trade_date"],
            "open": b["open"], "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"],
            "ma5": ma5[i], "ma10": ma10[i], "ma20": ma20[i],
            "dif": dif[i], "dea": dea[i], "macd": macd[i],
            "k": k[i], "d": d[i], "j": j[i],
            "strict_ok": strict_ok[i], "loose_ok": loose_ok[i], "golden_ok": golden_ok[i],
            "mid_reverse_ok": mid_reverse_ok[i], "stop_loss_ok": stop_loss_ok[i],
        })
    return {"code": code, "name": name, "period": period, "bars": out_bars}


def get_fundamentals_view(code: str, mention_days: int = 90) -> dict:
    """估值快照 + 最新财报 + 所属板块 + 大V提及帖子。"""
    quote = db.get_latest_row_by_code(code) or {}
    name = quote.get("name") or code
    return {
        "code": code,
        "name": name,
        "quote": {
            "pe_ttm": quote.get("pe_ttm"),
            "pb": quote.get("pb"),
            "total_mv": quote.get("total_mv"),
            "circ_mv": quote.get("circ_mv"),
        },
        "finance": db.get_finance_by_code(code),
        "sectors": db.get_sectors_by_code(code),
        "mentions": matching.get_stock_mentions(code, name, days=mention_days, limit=20),
    }


def group_members_view(group_id: int) -> list[dict]:
    """组内股票 + 最新行情快照，供渲染同款结果表格。"""
    members = db.get_group_members(group_id)
    latest_by_code = {r["code"]: r for r in db.get_latest_rows_by_codes([m["code"] for m in members])}
    rows = []
    for m in members:
        row = dict(latest_by_code.get(m["code"]) or {})
        row["code"] = m["code"]
        row["name"] = row.get("name") or m["name"] or m["code"]
        row["added_at"] = m["added_at"]
        rows.append(row)
    return rows
