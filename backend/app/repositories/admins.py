"""管理员账号仓储（Phase 3）。async 供登录/鉴权读；sync 供引导脚本 & lifespan 建号。"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sync_db import sync_session


async def get_by_username(session: AsyncSession, username: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, username, password_hash FROM admins WHERE username = :u"),
        {"u": username},
    )).mappings().first()
    return dict(row) if row else None


# ===== 同步（引导/脚本）=====
def count_admins() -> int:
    with sync_session() as s:
        return s.execute(text("SELECT COUNT(*) FROM admins")).scalar_one()


def create_admin(username: str, password_hash: str) -> int | None:
    """已存在同名返回 None。"""
    with sync_session() as s:
        row = s.execute(text(
            """
            INSERT INTO admins (username, password_hash, created_at)
            VALUES (:u, :h, :now)
            ON CONFLICT (username) DO NOTHING
            RETURNING id
            """
        ), {"u": username, "h": password_hash, "now": int(time.time())}).first()
        return row[0] if row else None
