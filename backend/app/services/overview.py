"""看板总览：复刻 web.py /api/overview 组装逻辑（异步）。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import posts as posts_repo
from app.repositories import sync_data as db
from app.services import matching


def get_bullish_heat(days: int = 7, limit: int = 20) -> list[dict]:
    """最近 days 天被最多大V看多的标的 Top N，供看板"看多热度榜"用。

    matching.get_bullish_users_map 按名称聚合"看多大V列表"；这里按大V数量排序取前 limit，
    再用最新快照补代码/现价/涨跌幅——总结里的名称在行情表找不到（简称/已退市等）的直接丢弃。
    走同步引擎，调用方须用 run_in_threadpool。
    """
    bullish_map = matching.get_bullish_users_map(days)
    if not bullish_map:
        return []
    row_by_name = {r["name"]: r for r in db.get_latest_rows_by_names(list(bullish_map)) if r.get("name")}
    items = []
    for name, users in bullish_map.items():
        row = row_by_name.get(name)
        if not row:
            continue
        items.append({
            "name": name,
            "code": row.get("code"),
            "close": row.get("close"),
            "change_pct": row.get("change_pct"),
            "bullish_count": len(users),
            "bullish_users": users,
        })
    items.sort(key=lambda x: x["bullish_count"], reverse=True)
    return items[:limit]


def get_board_bullish_heat(days: int = 7, limit: int = 20) -> list[dict]:
    """最近 days 天里，有 bullish 股票最多的板块/概念 Top N。

    以 get_bullish_users_map 的结果为基础，把 bullish 股票映射到所属板块，
    按"该板块下 bullish 股票数量"排序；kind 字段区分 industry/concept，供前端分tab展示。
    """
    bullish_map = matching.get_bullish_users_map(days)
    if not bullish_map:
        return []
    row_by_name = {r["name"]: r for r in db.get_latest_rows_by_names(list(bullish_map)) if r.get("name")}
    code_by_name = {n: row_by_name[n]["code"] for n in bullish_map if n in row_by_name and row_by_name[n].get("code")}
    if not code_by_name:
        return []
    by_code = db.get_sectors_by_codes(list(code_by_name.values()))
    agg: dict[str, dict] = {}
    for name, users in bullish_map.items():
        code = code_by_name.get(name)
        if not code:
            continue
        for sec in by_code.get(code, []):
            sname = sec["sector"]
            if sname not in agg:
                agg[sname] = {"sector": sname, "kind": sec["kind"] or "industry", "stocks": set(), "users": set()}
            agg[sname]["stocks"].add((name, code))
            agg[sname]["users"].update(users)
    items = [
        {
            "sector": v["sector"],
            "kind": v["kind"],
            "bullish_stock_count": len(v["stocks"]),
            "bullish_stocks": [{"name": n, "code": c} for n, c in sorted(v["stocks"])],
            "bullish_user_count": len(v["users"]),
            "bullish_users": sorted(v["users"]),
        }
        for v in agg.values()
    ]
    items.sort(key=lambda x: (x["bullish_stock_count"], x["bullish_user_count"]), reverse=True)
    return items[:limit]


async def build_overview(session: AsyncSession, user_id: str | None) -> dict:
    stats = await posts_repo.get_stats(session)
    monthly = await posts_repo.get_monthly_counts(session, user_id)
    daily = await posts_repo.get_daily_counts(session, user_id)
    latest = (await posts_repo.get_posts(session, user_id, limit=8, offset=0))["items"]

    total = sum(m["n"] for m in monthly) if user_id else stats["total"]
    span_first = daily[0]["date"] if daily else "-"
    span_last = daily[-1]["date"] if daily else "-"

    return {
        "total": total,
        "user_count": len(stats["per_user"]),
        "first": span_first,
        "last": span_last,
        "active_days": len(daily),
        "monthly": monthly,
        "daily": daily,
        "latest": latest,
    }
