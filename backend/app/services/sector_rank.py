"""板块行情聚合：成分股关系 × 最新交易日快照，纯库内聚合，无新数据源。"""
from app.repositories import sync_data as db


def get_rank() -> tuple[dict, int]:
    trade_date = db.get_latest_trade_date()
    if not trade_date:
        return {"error": "还没有行情数据，请先同步。", "items": [], "trade_date": None}, 400
    items = db.get_sector_rank(trade_date)
    return {"trade_date": trade_date, "items": items, "error": ""}, 200
