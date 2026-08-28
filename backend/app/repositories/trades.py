"""操作复盘记录仓储（异步）。"""
import time
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_trades(session: AsyncSession, user_id: str, code: Optional[str] = None, is_paper: bool = False) -> list[dict]:
    if code:
        rows = (await session.execute(text(
            "SELECT * FROM trade_records WHERE user_id = :uid AND code = :code AND is_paper = :ip ORDER BY trade_date DESC, id DESC"
        ), {"uid": user_id, "code": code, "ip": is_paper})).mappings().all()
    else:
        rows = (await session.execute(text(
            "SELECT * FROM trade_records WHERE user_id = :uid AND is_paper = :ip ORDER BY trade_date DESC, id DESC"
        ), {"uid": user_id, "ip": is_paper})).mappings().all()
    return [dict(r) for r in rows]


async def list_trades_by_date(session: AsyncSession, user_id: str, trade_date: str, is_paper: bool = False) -> list[dict]:
    rows = (await session.execute(text(
        "SELECT * FROM trade_records WHERE user_id = :uid AND trade_date = :d AND is_paper = :ip ORDER BY id ASC"
    ), {"uid": user_id, "d": trade_date, "ip": is_paper})).mappings().all()
    return [dict(r) for r in rows]


async def get_positions(session: AsyncSession, user_id: str, is_paper: bool = False) -> dict[str, dict]:
    """返回该用户所有股票的均价法持仓：{code: {name, avg_cost, hold_qty}}。"""
    rows = (await session.execute(text(
        "SELECT code, stock_name, direction, price, quantity FROM trade_records"
        " WHERE user_id = :uid AND is_paper = :ip ORDER BY trade_date ASC, id ASC"
    ), {"uid": user_id, "ip": is_paper})).mappings().all()
    pos: dict[str, dict] = {}
    for r in rows:
        code = r["code"]
        if code not in pos:
            pos[code] = {"name": r["stock_name"], "avg_cost": 0.0, "hold_qty": 0}
        m = pos[code]
        if r["direction"] == "buy":
            total = m["avg_cost"] * m["hold_qty"] + float(r["price"]) * r["quantity"]
            m["hold_qty"] += r["quantity"]
            m["avg_cost"] = total / m["hold_qty"] if m["hold_qty"] else 0.0
        else:
            m["hold_qty"] = max(0, m["hold_qty"] - r["quantity"])
    return pos


async def create_trade(session: AsyncSession, user_id: str, data: dict, is_paper: bool = False) -> dict:
    payload = {**data, "user_id": user_id, "created_at": int(time.time()), "is_paper": is_paper}
    row = (await session.execute(text(
        """
        INSERT INTO trade_records (code, stock_name, direction, price, quantity, trade_date, note, created_at, user_id, is_paper)
        VALUES (:code, :stock_name, :direction, :price, :quantity, :trade_date, :note, :created_at, :user_id, :is_paper)
        RETURNING *
        """
    ), payload)).mappings().one()
    await session.commit()
    return dict(row)


async def delete_trade(session: AsyncSession, user_id: str, trade_id: int) -> bool:
    result = await session.execute(
        text("DELETE FROM trade_records WHERE id = :id AND user_id = :uid"),
        {"id": trade_id, "uid": user_id},
    )
    await session.commit()
    return result.rowcount > 0


async def get_trade_stats(session: AsyncSession, user_id: str, is_paper: bool = False) -> dict:
    """均价法逐笔计算胜率，只统计卖出成交。"""
    rows = (await session.execute(text(
        "SELECT code, direction, price, quantity FROM trade_records"
        " WHERE user_id = :uid AND is_paper = :ip ORDER BY trade_date ASC, id ASC"
    ), {"uid": user_id, "ip": is_paper})).mappings().all()

    avg_cost: dict[str, float] = {}
    hold_qty: dict[str, float] = {}
    stock_realized: dict[str, float] = {}
    stock_has_sell: set[str] = set()
    win_pnl_sum = 0.0
    loss_pnl_sum = 0.0
    trade_wins = 0
    trade_losses = 0

    for r in rows:
        code = r["code"]
        price = float(r["price"])
        qty = int(r["quantity"])
        if code not in avg_cost:
            avg_cost[code] = 0.0
            hold_qty[code] = 0.0
        if r["direction"] == "buy":
            total = avg_cost[code] * hold_qty[code] + price * qty
            hold_qty[code] += qty
            avg_cost[code] = total / hold_qty[code] if hold_qty[code] else 0.0
        else:
            pnl = (price - avg_cost[code]) * qty
            stock_realized[code] = stock_realized.get(code, 0.0) + pnl
            stock_has_sell.add(code)
            if pnl > 0:
                trade_wins += 1
                win_pnl_sum += pnl
            else:
                trade_losses += 1
                loss_pnl_sum += abs(pnl)
            hold_qty[code] = max(0.0, hold_qty[code] - qty)

    total_stocks = len(stock_has_sell)
    win_stocks = sum(1 for c in stock_has_sell if stock_realized.get(c, 0.0) > 0)
    lose_stocks = total_stocks - win_stocks
    win_rate = win_stocks / total_stocks if total_stocks else 0.0
    total_trades = trade_wins + trade_losses
    avg_win = win_pnl_sum / trade_wins if trade_wins else 0.0
    avg_loss = loss_pnl_sum / trade_losses if trade_losses else 0.0
    profit_factor = win_pnl_sum / loss_pnl_sum if loss_pnl_sum else None
    return {
        "total_sell_trades": total_trades,
        "wins": win_stocks,
        "losses": lose_stocks,
        "total_stocks": total_stocks,
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "total_realized_pnl": round(win_pnl_sum - loss_pnl_sum, 2),
    }


async def get_backtest(session: AsyncSession, user_id: str, is_paper: bool = False) -> dict:
    """按均价法回放成交，返回已平仓交易、累计收益和权益曲线。"""
    rows = (await session.execute(text(
        "SELECT code, stock_name, direction, price, quantity, trade_date FROM trade_records "
        "WHERE user_id=:uid AND is_paper=:ip ORDER BY trade_date ASC, id ASC"
    ), {"uid": user_id, "ip": is_paper})).mappings().all()
    positions: dict[str, dict] = {}
    deals: list[dict] = []
    equity = 0.0
    curve: list[dict] = []
    for r in rows:
        code = r["code"]
        price = float(r["price"])
        quantity = int(r["quantity"])
        p = positions.setdefault(code, {"name": r["stock_name"], "cost": 0.0, "qty": 0})
        if r["direction"] == "buy":
            total = p["cost"] * p["qty"] + price * quantity
            p["qty"] += quantity
            p["cost"] = total / p["qty"] if p["qty"] else 0.0
        elif p["qty"] > 0:
            qty = min(quantity, p["qty"])
            pnl = (price - p["cost"]) * qty
            equity += pnl
            deals.append({"code": code, "name": p["name"], "trade_date": r["trade_date"], "quantity": qty, "buy_price": round(p["cost"], 4), "sell_price": price, "pnl": round(pnl, 2)})
            p["qty"] -= qty
            if p["qty"] == 0:
                p["cost"] = 0.0
        curve.append({"trade_date": r["trade_date"], "equity": round(equity, 2)})
    peak = 0.0
    max_drawdown = 0.0
    for point in curve:
        peak = max(peak, point["equity"])
        max_drawdown = max(max_drawdown, peak - point["equity"])
    wins = sum(1 for d in deals if d["pnl"] > 0)
    total = len(deals)
    return {"total_return": round(equity, 2), "max_drawdown": round(max_drawdown, 2), "win_rate": round(wins / total, 4) if total else 0.0, "trade_count": total, "wins": wins, "losses": total - wins, "trades": deals, "curve": curve}


async def bulk_import_trades(session: AsyncSession, user_id: str, records: list[dict], is_paper: bool = False) -> int:
    """批量导入，按 (user_id, code, trade_date, direction, price, quantity) 去重。"""
    now = int(time.time())
    imported = 0
    for r in records:
        existing = (await session.execute(text(
            """SELECT id FROM trade_records
               WHERE user_id=:uid AND code=:code AND trade_date=:trade_date
                 AND COALESCE(trade_time, '') = COALESCE(:trade_time, '')
                 AND direction=:direction AND price=:price AND quantity=:quantity AND is_paper=:ip"""
        ), {**r, "uid": user_id, "ip": is_paper})).first()
        if existing:
            continue
        await session.execute(text(
            """INSERT INTO trade_records (code, stock_name, direction, price, quantity, trade_date, trade_time, note, created_at, user_id, is_paper)
               VALUES (:code, :stock_name, :direction, :price, :quantity, :trade_date, :trade_time, :note, :created_at, :user_id, :is_paper)"""
        ), {**r, "trade_time": r.get("trade_time"), "note": r.get("note", ""), "created_at": now, "user_id": user_id, "is_paper": is_paper})
        imported += 1
    await session.commit()
    return imported
