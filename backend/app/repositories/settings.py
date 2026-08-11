"""用户级与系统级键值对设置仓储。"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_setting(session: AsyncSession, user_id: str, key: str) -> str | None:
    row = await session.execute(
        text("SELECT value_json FROM user_settings WHERE user_id=:u AND key=:k"),
        {"u": user_id, "k": key},
    )
    r = row.mappings().first()
    return r["value_json"] if r else None


async def upsert_user_setting(session: AsyncSession, user_id: str, key: str, value_json: str) -> None:
    now = int(time.time() * 1000)
    await session.execute(
        text(
            "INSERT INTO user_settings (user_id, key, value_json, updated_at) "
            "VALUES (:u, :k, :v, :t) "
            "ON CONFLICT (user_id, key) DO UPDATE "
            "SET value_json=EXCLUDED.value_json, updated_at=EXCLUDED.updated_at"
        ),
        {"u": user_id, "k": key, "v": value_json, "t": now},
    )
    await session.commit()


async def get_system_setting(session: AsyncSession, key: str) -> str | None:
    row = await session.execute(
        text("SELECT value_json FROM system_settings WHERE key=:k"),
        {"k": key},
    )
    r = row.mappings().first()
    return r["value_json"] if r else None


async def upsert_system_setting(session: AsyncSession, key: str, value_json: str) -> None:
    now = int(time.time() * 1000)
    await session.execute(
        text(
            "INSERT INTO system_settings (key, value_json, updated_at) "
            "VALUES (:k, :v, :t) "
            "ON CONFLICT (key) DO UPDATE "
            "SET value_json=EXCLUDED.value_json, updated_at=EXCLUDED.updated_at"
        ),
        {"k": key, "v": value_json, "t": now},
    )
    await session.commit()


async def delete_system_setting(session: AsyncSession, key: str) -> None:
    await session.execute(
        text("DELETE FROM system_settings WHERE key=:k"),
        {"k": key},
    )
    await session.commit()
