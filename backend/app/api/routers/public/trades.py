"""操作复盘记录接口。"""
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_visitor
from app.repositories import groups as groups_repo
from app.repositories import trades as trades_repo

router = APIRouter(prefix="/api")

_DIRECTIONS = {"买入", "卖出"}


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
    data = body.model_dump(exclude={"is_paper"})
    trade = await trades_repo.create_trade(session, user_id, data, body.is_paper)
    if not body.is_paper:
        await groups_repo.sync_auto_groups(session, user_id)
    return {"trade": trade, "error": ""}


@router.delete("/trades/{trade_id}")
async def api_delete_trade(
    trade_id: int,
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    ok = await trades_repo.delete_trade(session, user_id, trade_id)
    if not ok:
        raise HTTPException(404, "trade not found")
    if not is_paper:
        await groups_repo.sync_auto_groups(session, user_id)
    return {"error": ""}


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
    if not is_paper:
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
