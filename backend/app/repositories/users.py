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


async def set_password_by_email(session: AsyncSession, email: str, password_hash: str) -> bool:
    result = await session.execute(
        text("UPDATE users SET password_hash = :h WHERE email = :e"),
        {"h": password_hash, "e": email},
    )
    await session.commit()
    return result.rowcount > 0


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


async def _migrate_email_data(session: AsyncSession, old_sub: str, new_sub: str) -> None:
    """Merge old login-keyed data into the new email without unique-key failures."""
    # Merge same-name groups first, preserving all members and avoiding duplicate codes.
    await session.execute(text(
        """INSERT INTO stock_group_members (group_id, code, name, added_at)
           SELECT new_g.id, m.code, m.name, m.added_at
           FROM stock_groups old_g
           JOIN stock_groups new_g ON new_g.user_id=:new_sub
            AND new_g.name=old_g.name AND new_g.is_paper=old_g.is_paper
           JOIN stock_group_members m ON m.group_id=old_g.id
           WHERE old_g.user_id=:old_sub
           ON CONFLICT (group_id, code) DO NOTHING"""),
        {"old_sub": old_sub, "new_sub": new_sub})
    await session.execute(text(
        """DELETE FROM stock_group_members m USING stock_groups old_g, stock_groups new_g
           WHERE m.group_id=old_g.id AND old_g.user_id=:old_sub
            AND new_g.user_id=:new_sub AND new_g.name=old_g.name
            AND new_g.is_paper=old_g.is_paper"""),
        {"old_sub": old_sub, "new_sub": new_sub})
    await session.execute(text(
        """DELETE FROM stock_groups old_g USING stock_groups new_g
           WHERE old_g.user_id=:old_sub AND new_g.user_id=:new_sub
            AND new_g.name=old_g.name AND new_g.is_paper=old_g.is_paper"""),
        {"old_sub": old_sub, "new_sub": new_sub})

    # Keep the target-side copy when a user retries a partially completed change.
    await session.execute(text(
        """DELETE FROM trade_notes old_n USING trade_notes new_n
           WHERE old_n.user_id=:old_sub AND new_n.user_id=:new_sub
            AND old_n.note_date=new_n.note_date AND old_n.is_paper=new_n.is_paper"""),
        {"old_sub": old_sub, "new_sub": new_sub})
    await session.execute(text(
        """DELETE FROM user_settings old_s USING user_settings new_s
           WHERE old_s.user_id=:old_sub AND new_s.user_id=:new_sub
            AND old_s.key=new_s.key"""), {"old_sub": old_sub, "new_sub": new_sub})
    await session.execute(text(
        """DELETE FROM notification_events old_n USING notification_events new_n
           WHERE old_n.user_id=:old_sub AND new_n.user_id=:new_sub
            AND old_n.channel=new_n.channel AND old_n.event_key=new_n.event_key"""),
        {"old_sub": old_sub, "new_sub": new_sub})

    # The old account is authoritative: a failed first attempt may have created an empty target account.
    await session.execute(text(
        """INSERT INTO paper_accounts (user_id, balance, created_at)
           SELECT :new_sub, balance, created_at FROM paper_accounts
           WHERE user_id=:old_sub
           ON CONFLICT (user_id) DO UPDATE
             SET balance=EXCLUDED.balance, created_at=EXCLUDED.created_at"""),
        {"old_sub": old_sub, "new_sub": new_sub})
    await session.execute(text("DELETE FROM paper_accounts WHERE user_id=:old_sub"), {"old_sub": old_sub})

    for table in ("stock_groups", "trade_records", "trade_notes", "user_settings", "notification_events"):
        await session.execute(text(f"UPDATE {table} SET user_id=:new_sub WHERE user_id=:old_sub"),
                              {"old_sub": old_sub, "new_sub": new_sub})


async def change_email(session: AsyncSession, sub: str, email: str, migrate_data: bool = False) -> dict | None:
    """更换邮箱；邮箱登录账号同时迁移所有以旧邮箱为 user_id 的业务数据。"""
    if migrate_data and sub != email:
        await _migrate_email_data(session, sub, email)
    row = (await session.execute(
        text(
            "UPDATE users SET email=:email WHERE phone=:sub OR openid=:sub OR email=:sub "
            "RETURNING id, email, is_admin"
        ),
        {"sub": sub, "email": email},
    )).mappings().first()
    await session.commit()
    return dict(row) if row else None


async def bind_email(session: AsyncSession, sub: str, email: str) -> dict | None:
    """为没有邮箱的当前账号绑定邮箱，不改变其原有登录身份。"""
    row = (await session.execute(
        text(
            "UPDATE users SET email=:email WHERE email IS NULL "
            "AND (phone=:sub OR openid=:sub) RETURNING id, email, is_admin"
        ),
        {"sub": sub, "email": email},
    )).mappings().first()
    await session.commit()
    return dict(row) if row else None

