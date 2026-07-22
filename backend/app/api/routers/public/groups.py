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
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    await groups_repo.sync_auto_groups(session, user_id)
    return {"groups": await groups_repo.list_groups(session, user_id), "error": ""}


@router.get("/groups/{group_id}/members")
async def api_group_members(
    group_id: int,
    _uid: str = Depends(require_visitor),
):
    items = await run_in_threadpool(views.group_members_view, group_id)
    return {"items": items, "error": ""}


class CreateGroupBody(BaseModel):
    name: str


@router.post("/groups")
async def api_create_group(
    body: CreateGroupBody,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    if name in _RESERVED:
        raise HTTPException(400, f"「{name}」为系统保留分组名，不可手动创建")
    group = await groups_repo.create_group(session, name, user_id)
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
