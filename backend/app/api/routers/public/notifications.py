"""当前用户的站内通知。"""
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_visitor

router = APIRouter(prefix="/api/notifications")


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    limit = max(1, min(limit, 100))
    where = "AND read_at IS NULL" if unread_only else ""
    rows = (await session.execute(text(
        "SELECT id, title, content, sent_at, read_at FROM notification_events "
        "WHERE user_id=:u AND channel='in_app' " + where + " ORDER BY sent_at DESC, id DESC LIMIT :limit"
    ), {"u": user_id, "limit": limit})).mappings().all()
    unread = (await session.execute(text(
        "SELECT COUNT(*) FROM notification_events WHERE user_id=:u AND channel='in_app' AND read_at IS NULL"
    ), {"u": user_id})).scalar_one()
    return {"items": [dict(r) for r in rows], "unread": unread, "error": ""}


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: int, user_id: str = Depends(require_visitor), session: AsyncSession = Depends(db_session)):
    result = await session.execute(text(
        "UPDATE notification_events SET read_at=:t WHERE id=:id AND user_id=:u AND channel='in_app'"
    ), {"t": int(time.time()), "id": notification_id, "u": user_id})
    await session.commit()
    if not result.rowcount:
        raise HTTPException(404, "notification not found")
    return {"error": ""}


@router.post("/read-all")
async def mark_all_notifications_read(user_id: str = Depends(require_visitor), session: AsyncSession = Depends(db_session)):
    await session.execute(text(
        "UPDATE notification_events SET read_at=:t WHERE user_id=:u AND channel='in_app' AND read_at IS NULL"
    ), {"t": int(time.time()), "u": user_id})
    await session.commit()
    return {"error": ""}
