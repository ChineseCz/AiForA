"""个股详情页视图：K线 / 基本面 / 分组成员。从旧 stock.py 移植。数据走 sync_data。"""
from app.repositories import sync_data as db
from app.services import indicators, matching


def get_kline_view(code: str) -> dict:
    """日线K线 + MA/MACD/KDJ + 逐日买卖点信号，供前端画6幅图。"""
    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    name = (latest_by_code.get(code) or {}).get("name") or code

    bars = db.get_history_for_code(code)
    if len(bars) < 23:
        return {"code": code, "name": name, "bars": []}

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
            "open": b["open"] if b["open"] is not None else b["close"],
            "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"],
            "ma5": ma5[i], "ma10": ma10[i], "ma20": ma20[i],
            "dif": dif[i], "dea": dea[i], "macd": macd[i],
            "k": k[i], "d": d[i], "j": j[i],
            "strict_ok": strict_ok[i], "loose_ok": loose_ok[i], "golden_ok": golden_ok[i],
            "mid_reverse_ok": mid_reverse_ok[i], "stop_loss_ok": stop_loss_ok[i],
        })
    return {"code": code, "name": name, "bars": out_bars}


def get_fundamentals_view(code: str, mention_days: int = 90) -> dict:
    """估值快照 + 最新财报 + 所属板块 + 大V提及帖子。"""
    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    quote = latest_by_code.get(code) or {}
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
    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    rows = []
    for m in db.get_group_members(group_id):
        row = dict(latest_by_code.get(m["code"]) or {})
        row["code"] = m["code"]
        row["name"] = row.get("name") or m["name"] or m["code"]
        row["added_at"] = m["added_at"]
        rows.append(row)
    return rows
