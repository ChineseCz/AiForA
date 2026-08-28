"""操作复盘记录接口。"""
import re
from decimal import Decimal
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_visitor
from app.repositories import groups as groups_repo
from app.repositories import trades as trades_repo
from app.repositories import paper_accounts as paper_repo
from app.services.trade_screenshot import extract_trades

router = APIRouter(prefix="/api")

_DIRECTIONS = {"买入", "卖出"}


def _screenshot_key(row: dict) -> tuple:
    return (row.get("code", ""), row.get("stock_name", ""), row.get("direction", ""),
            float(row.get("price", 0)), int(row.get("quantity", 0)), row.get("trade_date", ""),
            row.get("trade_time") or "")


async def _prepare_screenshot_items(session: AsyncSession, user_id: str, raw: list[dict], is_paper: bool, default_date: str) -> list[dict]:
    result: list[dict] = []
    seen: set[tuple] = set()
    for item in raw:
        name = str(item.get("stock_name") or "").strip()
        direction = str(item.get("direction") or "").strip()
        direction = "买入" if direction in ("买入", "buy") else "卖出" if direction in ("卖出", "sell") else ""
        try:
            price, quantity = float(item.get("price")), int(item.get("quantity"))
        except (TypeError, ValueError):
            continue
        if not name or not direction or price <= 0 or quantity <= 0:
            continue
        trade_date = str(item.get("trade_date") or default_date)[:10]
        trade_time = str(item.get("trade_time") or "")[:8] or None
        candidates = (await session.execute(text(
            "SELECT code, name FROM stock_daily WHERE trade_date=(SELECT MAX(trade_date) FROM stock_daily) AND name ILIKE :name LIMIT 5"
        ), {"name": f"%{name}%"})).mappings().all()
        code = str(item.get("code") or "").strip()
        matched_name = name
        if not code and len(candidates) == 1:
            code, matched_name = candidates[0]["code"], candidates[0]["name"]
        row = {"code": code, "stock_name": matched_name, "direction": "buy" if direction == "买入" else "sell", "price": price, "quantity": quantity, "trade_date": trade_date, "trade_time": trade_time, "amount": item.get("amount")}
        key = _screenshot_key(row)
        exists = False
        if code:
            exists = bool((await session.execute(text(
                "SELECT 1 FROM trade_records WHERE user_id=:u AND is_paper=:p AND code=:c AND trade_date=:d AND COALESCE(trade_time,'')=COALESCE(:tt,'') AND direction=:dir AND price=:price AND quantity=:q LIMIT 1"
            ), {"u": user_id, "p": is_paper, "c": code, "d": trade_date, "tt": trade_time, "dir": row["direction"], "price": price, "q": quantity})).first())
        row["duplicate"] = exists or key in seen or not code or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", trade_date)
        row["candidates"] = [{"code": c["code"], "name": c["name"]} for c in candidates]
        seen.add(key)
        result.append(row)
    return result


@router.post("/trades/screenshot/preview")
async def api_screenshot_preview(
    files: list[UploadFile] = File(...),
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    if not files or len(files) > 6:
        raise HTTPException(400, "最多上传 6 张截图")
    images = []
    for file in files:
        data = await file.read()
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(400, "单张截图不能超过 8MB")
        images.append((data, file.content_type or "image/jpeg"))
    try:
        raw = await run_in_threadpool(extract_trades, images)
        items = await _prepare_screenshot_items(session, user_id, raw, is_paper, date.today().isoformat())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"截图识别失败：{exc}") from exc
    return {"items": items, "new_count": sum(not item["duplicate"] for item in items), "error": ""}


@router.post("/trades/screenshot/confirm")
async def api_screenshot_confirm(
    body: dict,
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    records = []
    for item in body.get("items", []):
        if item.get("duplicate") or not item.get("code"):
            continue
        try:
            records.append({"code": str(item["code"]), "stock_name": str(item.get("stock_name") or ""), "direction": item["direction"], "price": float(item["price"]), "quantity": int(item["quantity"]), "trade_date": str(item["trade_date"]), "trade_time": item.get("trade_time"), "note": "截图导入"})
        except (KeyError, TypeError, ValueError):
            continue
    imported = await trades_repo.bulk_import_trades(session, user_id, records, is_paper)
    if is_paper:
        await groups_repo.sync_paper_auto_groups(session, user_id)
    else:
        await groups_repo.sync_auto_groups(session, user_id)
    return {"imported": imported, "skipped": len(records) - imported, "error": ""}


def _parse_pingan_txt(content: bytes, filename: str = "") -> list[dict]:
    """解析平安证券成交查询 TXT（GBK，支持历史成交和当日成交两种格式）。

    历史成交：第一列为 YYYY-MM-DD，日期直接取自数据行。
    当日成交：第一列为 HH:MM:SS，日期从文件名 8 位数字前缀提取，否则用今天。
    """
    text_content = content.decode("gbk", errors="replace")

    m = re.search(r"(\d{8})", filename)
    if m:
        d = m.group(1)
        intraday_date = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    else:
        intraday_date = date.today().isoformat()

    records = []
    for line in text_content.splitlines():
        parts = line.split()
        if not parts or len(parts) < 10:
            continue

        first = parts[0]
        # 历史成交：YYYY-MM-DD
        if len(first) == 10 and first[4] == "-":
            dir_idx = next((i for i in range(4, min(9, len(parts))) if parts[i] in _DIRECTIONS), None)
            if dir_idx is None:
                continue
            try:
                name = "".join(parts[4:dir_idx])
                direction = "buy" if parts[dir_idx] == "买入" else "sell"
                price = float(parts[dir_idx + 3])
                quantity = int(parts[dir_idx + 4])
                trade_date = parts[dir_idx + 6]
                code = parts[3]
            except (IndexError, ValueError):
                continue

        # 当日成交：HH:MM:SS
        elif len(first) == 8 and first[2] == ":" and first[5] == ":":
            # cols: 委托时间 委托编号 证券代码 证券名称(可能含空格) 买卖标志 委托价格 委托数量 成交价格 成交数量 ...
            dir_idx = next((i for i in range(4, min(10, len(parts))) if parts[i] in _DIRECTIONS), None)
            if dir_idx is None:
                continue
            try:
                direction = "buy" if parts[dir_idx] == "买入" else "sell"
                code = parts[2]
                name = "".join(parts[3:dir_idx])
                price = float(parts[dir_idx + 3])   # 成交价格
                quantity = int(parts[dir_idx + 4])  # 成交数量
                trade_date = intraday_date
            except (IndexError, ValueError):
                continue

        else:
            continue

        if quantity <= 0:
            continue
        records.append({
            "code": code,
            "stock_name": name,
            "direction": direction,
            "price": price,
            "quantity": quantity,
            "trade_date": trade_date,
        })
    return records


@router.get("/trades")
async def api_list_trades(
    code: Optional[str] = None,
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    items = await trades_repo.list_trades(session, user_id, code, is_paper)
    return {"items": items, "error": ""}


class CreateTradeBody(BaseModel):
    code: str
    stock_name: str = ""
    direction: str  # buy | sell
    price: float
    quantity: int
    trade_date: str  # YYYY-MM-DD
    note: str = ""
    is_paper: bool = False


@router.post("/trades")
async def api_create_trade(
    body: CreateTradeBody,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    if body.direction not in ("buy", "sell"):
        raise HTTPException(400, "direction must be buy or sell")
    if body.is_paper:
        amount = Decimal(str(body.price)) * body.quantity
        if body.direction == "buy":
            await paper_repo.debit(session, user_id, amount)
        else:
            await paper_repo.credit(session, user_id, amount)
    data = body.model_dump(exclude={"is_paper"})
    trade = await trades_repo.create_trade(session, user_id, data, body.is_paper)
    if body.is_paper:
        await groups_repo.sync_paper_auto_groups(session, user_id)
    else:
        await groups_repo.sync_auto_groups(session, user_id)
    return {"trade": trade, "error": ""}


@router.delete("/trades/{trade_id}")
async def api_delete_trade(
    trade_id: int,
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    if is_paper:
        row = await session.execute(
            text(
                "SELECT direction, price, quantity FROM trade_records "
                "WHERE id=:id AND user_id=:u AND is_paper=true"
            ),
            {"id": trade_id, "u": user_id},
        )
        orig = row.mappings().first()
    else:
        orig = None
    ok = await trades_repo.delete_trade(session, user_id, trade_id)
    if not ok:
        raise HTTPException(404, "trade not found")
    if is_paper and orig:
        amount = Decimal(str(orig["price"])) * orig["quantity"]
        if orig["direction"] == "buy":
            await paper_repo.credit(session, user_id, amount)
        else:
            await paper_repo.debit(session, user_id, amount)
    if is_paper:
        await groups_repo.sync_paper_auto_groups(session, user_id)
    else:
        await groups_repo.sync_auto_groups(session, user_id)
    return {"error": ""}


@router.get("/trades/paper-account")
async def api_paper_account(
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    account = await paper_repo.get_or_create(session, user_id)
    return {"balance": account["balance"], "error": ""}


class ResetPaperBody(BaseModel):
    capital: float = 100000


@router.post("/trades/paper-account/reset")
async def api_reset_paper_account(
    body: ResetPaperBody,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    """清空模拟盘交易记录并重置初始资金。"""
    if body.capital <= 0:
        raise HTTPException(400, "capital 必须大于 0")
    await session.execute(
        text("DELETE FROM trade_records WHERE user_id=:u AND is_paper=true"),
        {"u": user_id},
    )
    await session.execute(
        text(
            "INSERT INTO paper_accounts (user_id, balance, created_at) VALUES (:u, :b, :t) "
            "ON CONFLICT (user_id) DO UPDATE SET balance=:b"
        ),
        {"u": user_id, "b": Decimal(str(body.capital)), "t": int(__import__("time").time() * 1000)},
    )
    await groups_repo.sync_paper_auto_groups(session, user_id)
    await session.commit()
    return {"balance": body.capital, "error": ""}


@router.post("/trades/import")
async def api_import_trades(
    file: UploadFile = File(...),
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    content = await file.read()
    try:
        records = _parse_pingan_txt(content, filename=file.filename or "")
    except Exception as e:
        raise HTTPException(400, f"解析失败: {e}")
    if not records:
        raise HTTPException(400, "未识别到任何成交记录，请确认文件格式")
    imported = await trades_repo.bulk_import_trades(session, user_id, records, is_paper)
    if is_paper:
        await groups_repo.sync_paper_auto_groups(session, user_id)
    else:
        await groups_repo.sync_auto_groups(session, user_id)
    return {"imported": imported, "total": len(records), "error": ""}


@router.get("/trades/stats")
async def api_trade_stats(
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    stats = await trades_repo.get_trade_stats(session, user_id, is_paper)
    return {"stats": stats, "error": ""}


@router.get("/trades/backtest")
async def api_trade_backtest(
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    return {"backtest": await trades_repo.get_backtest(session, user_id, is_paper), "error": ""}
