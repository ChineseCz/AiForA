"""自选股分组仓储（读 + 写）。"""
import time

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


async def create_group(session: AsyncSession, name: str) -> dict:
    now = int(time.time())
    row = (await session.execute(text(
        "INSERT INTO stock_groups (name, created_at) VALUES (:name, :ts) RETURNING id, name, created_at"
    ), {"name": name, "ts": now})).mappings().one()
    await session.commit()
    return {**dict(row), "member_count": 0}


async def delete_group(session: AsyncSession, group_id: int) -> bool:
    await session.execute(text("DELETE FROM stock_group_members WHERE group_id = :id"), {"id": group_id})
    result = await session.execute(text("DELETE FROM stock_groups WHERE id = :id"), {"id": group_id})
    await session.commit()
    return result.rowcount > 0


async def add_members(session: AsyncSession, group_id: int, stocks: list[dict]) -> None:
    now = int(time.time())
    for s in stocks:
        await session.execute(text(
            """
            INSERT INTO stock_group_members (group_id, code, name, added_at)
            VALUES (:gid, :code, :name, :ts)
            ON CONFLICT (group_id, code) DO NOTHING
            """
        ), {"gid": group_id, "code": s["code"], "name": s.get("name", ""), "ts": now})
    await session.commit()


async def remove_member(session: AsyncSession, group_id: int, code: str) -> bool:
    result = await session.execute(
        text("DELETE FROM stock_group_members WHERE group_id = :gid AND code = :code"),
        {"gid": group_id, "code": code},
    )
    await session.commit()
    return result.rowcount > 0
