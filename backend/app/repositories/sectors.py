"""板块名录的异步读仓储。"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_sector_catalog(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(text(
        "SELECT board_code, name, kind FROM sector_catalog ORDER BY kind, name"
    ))).mappings().all()
    return [dict(r) for r in rows]
