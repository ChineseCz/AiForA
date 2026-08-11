"""模拟盘资金账户仓储。"""
import time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_INITIAL_BALANCE = Decimal("100000")


async def get_or_create(session: AsyncSession, user_id: str) -> dict:
    row = await session.execute(
        text("SELECT balance FROM paper_accounts WHERE user_id=:u"),
        {"u": user_id},
    )
    r = row.mappings().first()
    if r:
        return {"balance": float(r["balance"])}
    now = int(time.time() * 1000)
    await session.execute(
        text(
            "INSERT INTO paper_accounts (user_id, balance, created_at) "
            "VALUES (:u, :b, :t) ON CONFLICT DO NOTHING"
        ),
        {"u": user_id, "b": _INITIAL_BALANCE, "t": now},
    )
    await session.commit()
    return {"balance": float(_INITIAL_BALANCE)}


async def debit(session: AsyncSession, user_id: str, amount: Decimal) -> float:
    """扣减余额（买入）。余额不足时抛 HTTPException 400。返回新余额。"""
    now = int(time.time() * 1000)
    # 确保账户存在
    await session.execute(
        text(
            "INSERT INTO paper_accounts (user_id, balance, created_at) "
            "VALUES (:u, :b, :t) ON CONFLICT DO NOTHING"
        ),
        {"u": user_id, "b": _INITIAL_BALANCE, "t": now},
    )
    # 原子扣减：balance >= amount 才更新
    row = await session.execute(
        text(
            "UPDATE paper_accounts SET balance = balance - :a "
            "WHERE user_id = :u AND balance >= :a RETURNING balance"
        ),
        {"a": amount, "u": user_id},
    )
    r = row.mappings().first()
    if r is None:
        await session.rollback()
        bal = await session.execute(
            text("SELECT balance FROM paper_accounts WHERE user_id=:u"),
            {"u": user_id},
        )
        current = (bal.scalar_one_or_none() or 0)
        raise HTTPException(400, f"余额不足：当前 {float(current):.2f}，需要 {float(amount):.2f}")
    await session.commit()
    return float(r["balance"])


async def credit(session: AsyncSession, user_id: str, amount: Decimal) -> float:
    """增加余额（卖出/撤销买入）。返回新余额。"""
    now = int(time.time() * 1000)
    await session.execute(
        text(
            "INSERT INTO paper_accounts (user_id, balance, created_at) "
            "VALUES (:u, :b, :t) ON CONFLICT DO NOTHING"
        ),
        {"u": user_id, "b": _INITIAL_BALANCE, "t": now},
    )
    row = await session.execute(
        text(
            "UPDATE paper_accounts SET balance = balance + :a "
            "WHERE user_id = :u RETURNING balance"
        ),
        {"a": amount, "u": user_id},
    )
    r = row.mappings().first()
    await session.commit()
    return float(r["balance"]) if r else float(_INITIAL_BALANCE + amount)
