"""选股接口编排：忠实复刻 web.py 的 /api/screen 与 /api/screen/preset 路由逻辑。

整体为同步（内部选股计算重），由路由用 run_in_threadpool 调用。返回 (payload, status_code)，
路由据此设状态码，保证与旧 Flask 行为（含 400 错误体）一致。
"""
from app.repositories import sync_data as db
from app.services import matching, screening


def _parse_user_ids(cfg: dict) -> list[str]:
    """兼容旧的单选 user_id（字符串）和新的多选 user_ids（数组），空 = 全部大V。"""
    ids = cfg.get("user_ids")
    if isinstance(ids, list) and ids:
        return [str(u) for u in ids if u]
    single = str(cfg.get("user_id") or "")
    return [single] if single else []


def screen(body: dict) -> tuple[dict, int]:
    trade_date = db.get_latest_trade_date()
    if not trade_date:
        return {"error": "还没有行情数据，请先同步。", "items": [], "trade_date": None}, 400

    conditions = body.get("conditions") or []
    strategies = [s for s in (body.get("strategies") or []) if s]
    name_query = str(body.get("name_query") or "").strip()

    try:
        limit = min(500, max(1, int(body.get("limit", 200) or 200)))
    except (TypeError, ValueError):
        limit = 200

    mentioned = body.get("mentioned") or {}
    sector = body.get("sector") or {}
    no_strategy_filter_on = bool(mentioned.get("enabled")) or bool(sector.get("enabled"))

    strategy_params = body.get("strategy_params") or {}

    try:
        if strategies:
            rows = screening.screen_combined_all(strategies, conditions, limit, strategy_params)
        elif conditions:
            where_sql, params = screening.build_where(conditions)
            rows = db.screen_stocks(trade_date, where_sql, params, limit)
        elif name_query or no_strategy_filter_on:
            # 没选预设策略/条件，但要靠"大V提及"或"板块"来筛——用全市场最新行情做候选池，
            # 交给下面的 match_mentions/match_sector 去缩小范围。
            rows = db.get_latest_rows()
        else:
            return {
                "error": "请至少选择一个预设策略、填写筛选条件、输入股票名称/代码，或勾选大V提及/板块筛选。",
                "items": [], "trade_date": trade_date,
            }, 400
    except (ValueError, screening.InsufficientHistoryError, screening.InsufficientFinanceError) as e:
        return {"error": str(e), "items": [], "trade_date": trade_date}, 400

    if name_query:
        rows = matching.match_name_query(rows, name_query)[:limit]

    if mentioned.get("enabled"):
        try:
            days = max(1, int(mentioned.get("days", 7) or 7))
        except (TypeError, ValueError):
            days = 7
        user_ids = _parse_user_ids(mentioned)
        rows = matching.match_mentions(rows, days, user_ids)
        if mentioned.get("bullish_only"):
            rows = matching.filter_bullish(rows, days, user_ids)

    if sector.get("enabled"):
        names = [n for n in (sector.get("names") or []) if n]
        if sector.get("mode") == "bullish":
            try:
                days = max(1, int(sector.get("days", 7) or 7))
            except (TypeError, ValueError):
                days = 7
            user_ids = _parse_user_ids(sector)
            names = matching.derive_bullish_sectors(days, user_ids)
        rows = matching.match_sector(rows, names) if names else []

    rows = rows[:limit]
    matching.attach_sectors(rows)
    matching.attach_bullish_users(rows)
    return {"trade_date": trade_date, "items": rows, "error": ""}, 200


def preset(body: dict) -> tuple[dict, int]:
    strategies = body.get("strategies")
    if not strategies:
        single = body.get("strategy")
        strategies = [single] if single else []

    trade_date = db.get_latest_trade_date()
    if not trade_date:
        return {"error": "还没有行情数据，请先同步。", "items": [], "trade_date": None}, 400

    try:
        limit = min(500, max(1, int(body.get("limit", 200) or 200)))
    except (TypeError, ValueError):
        limit = 200

    strategy_params = body.get("strategy_params") or {}

    try:
        rows = screening.screen_combined(strategies, limit, strategy_params)
    except (screening.InsufficientHistoryError, screening.InsufficientFinanceError, ValueError) as e:
        return {"error": str(e), "items": [], "trade_date": trade_date}, 400

    matching.attach_sectors(rows)
    matching.attach_bullish_users(rows)
    return {"trade_date": trade_date, "items": rows, "error": ""}, 200
