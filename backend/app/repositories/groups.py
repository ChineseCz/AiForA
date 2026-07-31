"""自选股分组仓储（读 + 写）。"""
import time
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_RESERVED_NAMES = ("持仓", "清仓")


async def list_groups(session: AsyncSession, user_id: str, is_paper: bool = False) -> list[dict]:
    rows = (await session.execute(text(
        """
        SELECT g.id, g.name, g.created_at, COUNT(m.code) AS member_count
        FROM stock_groups g
        LEFT JOIN stock_group_members m ON m.group_id = g.id
        WHERE (g.user_id = :uid OR g.user_id IS NULL) AND g.is_paper = :ip
        GROUP BY g.id, g.name, g.created_at
        ORDER BY g.created_at ASC
        """
    ), {"uid": user_id, "ip": is_paper})).mappings().all()
    return [dict(r) for r in rows]


async def create_group(session: AsyncSession, name: str, user_id: str, is_paper: bool = False) -> dict | None:
    """返回新分组；名称已存在则返回 None。"""
    now = int(time.time())
    row = (await session.execute(text(
        """
        INSERT INTO stock_groups (name, created_at, user_id, is_paper)
        VALUES (:name, :ts, :uid, :ip)
        ON CONFLICT (user_id, name, is_paper) DO NOTHING
        RETURNING id, name, created_at, user_id, is_paper
        """
    ), {"name": name, "ts": now, "uid": user_id, "ip": is_paper})).mappings().first()
    if not row:
        return None
    await session.commit()
    return {**dict(row), "member_count": 0}


async def delete_group(session: AsyncSession, group_id: int, user_id: str) -> bool:
    await session.execute(text("DELETE FROM stock_group_members WHERE group_id = :id"), {"id": group_id})
    result = await session.execute(
        text("DELETE FROM stock_groups WHERE id = :id AND user_id = :uid"),
        {"id": group_id, "uid": user_id},
    )
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


async def _get_or_create_group_id(session: AsyncSession, user_id: str, name: str, is_paper: bool = False) -> int:
    row = (await session.execute(text(
        "SELECT id FROM stock_groups WHERE user_id = :uid AND name = :n AND is_paper = :ip"
    ), {"uid": user_id, "n": name, "ip": is_paper})).first()
    if row:
        return row[0]
    now = int(time.time())
    row = (await session.execute(text(
        "INSERT INTO stock_groups (name, created_at, user_id, is_paper) VALUES (:n, :ts, :uid, :ip) RETURNING id"
    ), {"n": name, "ts": now, "uid": user_id, "ip": is_paper})).first()
    return row[0]


async def _replace_members(session: AsyncSession, group_id: int, stocks: list[dict]) -> None:
    """全量替换成员（保证幂等）。"""
    await session.execute(
        text("DELETE FROM stock_group_members WHERE group_id = :gid"),
        {"gid": group_id},
    )
    if not stocks:
        return
    now = int(time.time())
    for s in stocks:
        await session.execute(text(
            """
            INSERT INTO stock_group_members (group_id, code, name, added_at)
            VALUES (:gid, :code, :name, :ts)
            ON CONFLICT (group_id, code) DO NOTHING
            """
        ), {"gid": group_id, "code": s["code"], "name": s.get("name", ""), "ts": now})


async def sync_auto_groups(session: AsyncSession, user_id: str) -> None:
    """按实盘 trade_records 自动同步「持仓」和「清仓」分组（仅针对 is_paper=False）。"""
    try:
        rows = (await session.execute(text(
            "SELECT code, stock_name, direction, quantity, trade_date"
            " FROM trade_records WHERE user_id = :uid AND is_paper = FALSE ORDER BY trade_date ASC, id ASC"
        ), {"uid": user_id})).mappings().all()

        hold_qty: dict[str, int] = {}
        stock_name: dict[str, str] = {}
        cleared: dict[str, str] = {}

        for r in rows:
            code = r["code"]
            hold_qty.setdefault(code, 0)
            stock_name.setdefault(code, r["stock_name"])
            if r["direction"] == "buy":
                hold_qty[code] += r["quantity"]
            else:
                new_qty = max(0, hold_qty[code] - r["quantity"])
                if hold_qty[code] > 0 and new_qty == 0:
                    cleared[code] = r["trade_date"]
                hold_qty[code] = new_qty

        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        held = [{"code": c, "name": stock_name[c]} for c, q in hold_qty.items() if q > 0]
        recently_cleared = [
            {"code": c, "name": stock_name[c]}
            for c, d in cleared.items()
            if hold_qty.get(c, 0) == 0 and d >= cutoff
        ]

        hold_gid = await _get_or_create_group_id(session, user_id, "持仓", is_paper=False)
        await _replace_members(session, hold_gid, held)

        clear_gid = await _get_or_create_group_id(session, user_id, "清仓", is_paper=False)
        await _replace_members(session, clear_gid, recently_cleared)

        await session.commit()
    except Exception as e:  # noqa: BLE001
        print(f"[sync_auto_groups] 自动分组同步出错，user={user_id}: {e}")
