"""总结缓存的异步读仓储。"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_summary(session: AsyncSession, user_id: str, period_type: str, period_key: str) -> str | None:
    row = (await session.execute(text(
        "SELECT content FROM summaries WHERE user_id = :u AND period_type = :t AND period_key = :k"
    ), {"u": user_id, "t": period_type, "k": period_key})).first()
    return row[0] if row else None


async def get_summary_keys(session: AsyncSession, user_id: str, period_type: str) -> list[str]:
    rows = (await session.execute(text(
        """
        SELECT period_key FROM summaries
        WHERE user_id = :u AND period_type = :t
        ORDER BY period_key DESC
        """
    ), {"u": user_id, "t": period_type})).all()
    return [r[0] for r in rows]
