"""访客账号仓储（Phase 9）：手机号+验证码 / 微信扫码登录，异步读写。"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_by_phone(session: AsyncSession, phone: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, phone, nickname, created_at FROM users WHERE phone = :p"),
        {"p": phone},
    )).mappings().first()
    return dict(row) if row else None


async def get_or_create_by_phone(session: AsyncSession, phone: str) -> dict:
    """手机号首次登录即建号；已存在直接返回。"""
    await session.execute(
        text(
            "INSERT INTO users (phone, created_at) VALUES (:p, :now)"
            " ON CONFLICT (phone) DO NOTHING"
        ),
        {"p": phone, "now": int(time.time())},
    )
    await session.commit()
    row = await get_by_phone(session, phone)
    if row is None:
        raise RuntimeError(f"INSERT OR IGNORE succeeded but phone row not found: {phone!r}")
    return row


async def get_by_openid(session: AsyncSession, openid: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, openid, nickname, created_at FROM users WHERE openid = :oid"),
        {"oid": openid},
    )).mappings().first()
    return dict(row) if row else None


async def get_or_create_by_openid(session: AsyncSession, openid: str) -> dict:
    """微信openid首次登录即建号；已存在直接返回。"""
    await session.execute(
        text(
            "INSERT INTO users (openid, created_at) VALUES (:oid, :now)"
            " ON CONFLICT (openid) DO NOTHING"
        ),
        {"oid": openid, "now": int(time.time())},
    )
    await session.commit()
    row = await get_by_openid(session, openid)
    if row is None:
        raise RuntimeError(f"INSERT OR IGNORE succeeded but openid row not found: {openid!r}")
    return row


async def get_by_email(session: AsyncSession, email: str) -> dict | None:
    row = (await session.execute(
        text("SELECT id, email, password_hash, nickname, is_admin, created_at FROM users WHERE email = :e"),
        {"e": email},
    )).mappings().first()
    return dict(row) if row else None


async def create_by_email(session: AsyncSession, email: str, password_hash: str) -> dict:
    """邮箱验证码校验通过后建号；email 已注册时返回 None 由调用方判断。"""
    result = await session.execute(
        text(
            "INSERT INTO users (email, password_hash, created_at) VALUES (:e, :ph, :now)"
            " ON CONFLICT (email) DO NOTHING RETURNING id"
        ),
        {"e": email, "ph": password_hash, "now": int(time.time())},
    )
    inserted = result.first()
    await session.commit()
    if not inserted:
        return None
    row = await get_by_email(session, email)
    if row is None:
        raise RuntimeError(f"INSERT RETURNING succeeded but email row not found: {email!r}")
    return row


async def set_nickname(session: AsyncSession, sub: str, nickname: str) -> None:
    """sub 是 JWT 里的用户标识：手机号登录时是手机号，微信登录时是 openid。"""
    await session.execute(
        text("UPDATE users SET nickname = :n WHERE phone = :sub OR openid = :sub OR email = :sub"),
        {"n": nickname, "sub": sub},
    )
    await session.commit()

