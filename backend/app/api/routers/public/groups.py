"""自选分组：读 + 写（列表 / 成员 / 创建 / 删除）。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_visitor
from app.repositories import groups as groups_repo
from app.services import views

router = APIRouter(prefix="/api")

_RESERVED = {"持仓", "清仓"}


@router.get("/groups")
async def api_groups(
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    if is_paper:
        await groups_repo.sync_paper_auto_groups(session, user_id)
    else:
        await groups_repo.sync_auto_groups(session, user_id)
    return {"groups": await groups_repo.list_groups(session, user_id, is_paper), "error": ""}


@router.get("/groups/overview")
async def api_groups_overview(
    is_paper: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    """当前用户全部自选股的去重行情概览，避免前端逐组拉取后再聚合。"""
    from sqlalchemy import text

    rows = (await session.execute(text(
        """
        WITH watchlist AS (
          SELECT DISTINCT m.code, m.name
          FROM stock_groups g
          JOIN stock_group_members m ON m.group_id = g.id
          WHERE g.user_id = :uid AND g.is_paper = :is_paper
        ), latest AS (
          SELECT sd.code, COALESCE(sd.name, w.name, sd.code) AS name, sd.close, sd.change_pct, sd.trade_date,
                 si.cross1, si.cross23, si.rise5, si.price_above20, si.duotou, si.macd_recent, si.kdj_recent
          FROM watchlist w
          LEFT JOIN stock_daily sd ON sd.code = w.code
            AND sd.trade_date = (SELECT MAX(trade_date) FROM stock_daily)
          LEFT JOIN stock_indicator si ON si.code = w.code AND si.trade_date = sd.trade_date
        )
        SELECT * FROM latest
        """
    ), {"uid": user_id, "is_paper": is_paper})).mappings().all()
    items = [dict(row) for row in rows]
    quoted = [item for item in items if item.get("change_pct") is not None]
    signals = []
    for item in items:
        label = ""
        if item.get("cross1") and item.get("cross23") and item.get("rise5"):
            label = "严格买点" if item.get("price_above20") and item.get("duotou") else "宽松买点"
        elif item.get("macd_recent") and item.get("kdj_recent"):
            label = "金叉买点"
        if label:
            signals.append({"code": item["code"], "name": item["name"], "label": label})
    by_change_desc = sorted(quoted, key=lambda item: item["change_pct"], reverse=True)
    return {
        "total": len(items),
        "up": sum(1 for item in quoted if item["change_pct"] > 0),
        "down": sum(1 for item in quoted if item["change_pct"] < 0),
        "flat": sum(1 for item in quoted if item["change_pct"] == 0),
        "avg_change": sum(item["change_pct"] for item in quoted) / len(quoted) if quoted else None,
        "trade_date": next((item.get("trade_date") for item in items if item.get("trade_date")), None),
        "signals": signals,
        "gainers": [{"code": item["code"], "name": item["name"], "change_pct": item["change_pct"]} for item in by_change_desc[:3]],
        "losers": [{"code": item["code"], "name": item["name"], "change_pct": item["change_pct"]} for item in by_change_desc[-3:][::-1]],
    }


@router.get("/groups/{group_id}/members")
async def api_group_members(
    group_id: int,
    _uid: str = Depends(require_visitor),
):
    items = await run_in_threadpool(views.group_members_view, group_id)
    return {"items": items, "error": ""}


class CreateGroupBody(BaseModel):
    name: str
    is_paper: bool = False


@router.post("/groups")
async def api_create_group(
    body: CreateGroupBody,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    if name in _RESERVED and not body.is_paper:
        raise HTTPException(400, f"「{name}」为系统保留分组名，不可手动创建")
    group = await groups_repo.create_group(session, name, user_id, body.is_paper)
    if group is None:
        raise HTTPException(400, "分组名已存在")
    return {"group": group, "error": ""}


@router.delete("/groups/{group_id}")
async def api_delete_group(
    group_id: int,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    ok = await groups_repo.delete_group(session, group_id, user_id)
    if not ok:
        raise HTTPException(404, "group not found")
    return {"error": ""}


class AddMembersBody(BaseModel):
    stocks: list[dict]


@router.post("/groups/{group_id}/members")
async def api_add_members(
    group_id: int,
    body: AddMembersBody,
    _uid: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    await groups_repo.add_members(session, group_id, body.stocks)
    return {"error": ""}


@router.delete("/groups/{group_id}/members/{code}")
async def api_remove_member(
    group_id: int,
    code: str,
    _uid: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    ok = await groups_repo.remove_member(session, group_id, code)
    if not ok:
        raise HTTPException(404, "member not found")
    return {"error": ""}
