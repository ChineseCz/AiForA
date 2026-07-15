"""复盘每日笔记 repository。"""
import time
from datetime import date as _date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _to_date(s: str) -> _date:
    return _date.fromisoformat(s)


async def get_note(session: AsyncSession, user_id: str, note_date: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, note_date::text, content, updated_at, is_favorite FROM trade_notes WHERE user_id = :uid AND note_date = :d"),
        {"uid": user_id, "d": _to_date(note_date)},
    )).mappings().first()
    return dict(row) if row else None


async def upsert_note(session: AsyncSession, user_id: str, note_date: str, content: str) -> dict:
    now = int(time.time())
    row = (await session.execute(
        text("""
            INSERT INTO trade_notes (user_id, note_date, content, created_at, updated_at)
            VALUES (:uid, :d, :c, :now, :now)
            ON CONFLICT (user_id, note_date) DO UPDATE
              SET content = EXCLUDED.content, updated_at = EXCLUDED.updated_at
            RETURNING id, note_date::text, content, updated_at, is_favorite
        """),
        {"uid": user_id, "d": _to_date(note_date), "c": content, "now": now},
    )).mappings().first()
    await session.commit()
    return dict(row)


async def toggle_favorite(session: AsyncSession, user_id: str, note_date: str) -> dict | None:
    row = (await session.execute(
        text("""
            UPDATE trade_notes SET is_favorite = NOT is_favorite
            WHERE user_id = :uid AND note_date = :d
            RETURNING id, note_date::text, content, updated_at, is_favorite
        """),
        {"uid": user_id, "d": _to_date(note_date)},
    )).mappings().first()
    await session.commit()
    return dict(row) if row else None


async def list_notes(
    session: AsyncSession,
    user_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    favorite_only: bool = False,
) -> tuple[list[dict], int]:
    where = "WHERE user_id = :uid"
    params: dict = {"uid": user_id}
    if start_date:
        where += " AND note_date >= :s"
        params["s"] = _to_date(start_date)
    if end_date:
        where += " AND note_date <= :e"
        params["e"] = _to_date(end_date)
    if favorite_only:
        where += " AND is_favorite = TRUE"

    total = (await session.execute(
        text(f"SELECT count(*) FROM trade_notes {where}"), params,
    )).scalar_one()

    rows = (await session.execute(
        text(
            f"SELECT id, note_date::text, content, updated_at, is_favorite FROM trade_notes {where}"
            " ORDER BY note_date DESC LIMIT :lim OFFSET :off"
        ),
        {**params, "lim": page_size, "off": (page - 1) * page_size},
    )).mappings().all()
    return [dict(r) for r in rows], total


async def delete_note(session: AsyncSession, user_id: str, note_date: str) -> bool:
    result = await session.execute(
        text("DELETE FROM trade_notes WHERE user_id = :uid AND note_date = :d"),
        {"uid": user_id, "d": _to_date(note_date)},
    )
    await session.commit()
    return result.rowcount > 0


async def list_all_note_dates(session: AsyncSession, user_id: str) -> list[str]:
    rows = (await session.execute(
        text("SELECT note_date::text FROM trade_notes WHERE user_id = :uid ORDER BY note_date ASC"),
        {"uid": user_id},
    )).all()
    return [r[0] for r in rows]


async def list_dates_with_trades_in_range(
    session: AsyncSession, user_id: str, start_date: str, end_date: str
) -> list[str]:
    rows = (await session.execute(
        text("""
            SELECT DISTINCT trade_date::text
            FROM trade_records
            WHERE user_id = :uid AND trade_date BETWEEN :s AND :e
            ORDER BY trade_date ASC
        """),
        {"uid": user_id, "s": start_date, "e": end_date},
    )).all()
    return [r[0] for r in rows]
