"""自选股分组的异步读仓储（写操作留 Phase 2 管理员接口）。"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_groups(session: AsyncSession) -> list[dict]:
    rows = (await session.execute(text(
        """
        SELECT g.id, g.name, g.created_at, COUNT(m.code) AS member_count
        FROM stock_groups g
        LEFT JOIN stock_group_members m ON m.group_id = g.id
        GROUP BY g.id, g.name, g.created_at
        ORDER BY g.created_at DESC
        """
    ))).mappings().all()
    return [dict(r) for r in rows]
