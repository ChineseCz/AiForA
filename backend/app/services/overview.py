"""看板总览：复刻 web.py /api/overview 组装逻辑（异步）。"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import posts as posts_repo


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
