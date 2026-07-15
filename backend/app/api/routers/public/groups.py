"""自选分组：读 + 写（列表 / 成员 / 创建 / 删除）。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.repositories import groups as groups_repo
from app.services import views

router = APIRouter(prefix="/api")


@router.get("/groups")
async def api_groups(session: AsyncSession = Depends(db_session)):
    return {"groups": await groups_repo.list_groups(session), "error": ""}


@router.get("/groups/{group_id}/members")
async def api_group_members(group_id: int):
    items = await run_in_threadpool(views.group_members_view, group_id)
    return {"items": items, "error": ""}


class CreateGroupBody(BaseModel):
    name: str


@router.post("/groups")
async def api_create_group(body: CreateGroupBody, session: AsyncSession = Depends(db_session)):
    if not body.name.strip():
        raise HTTPException(400, "name required")
    group = await groups_repo.create_group(session, body.name.strip())
    return {"group": group, "error": ""}


@router.delete("/groups/{group_id}")
async def api_delete_group(group_id: int, session: AsyncSession = Depends(db_session)):
    ok = await groups_repo.delete_group(session, group_id)
    if not ok:
        raise HTTPException(404, "group not found")
    return {"error": ""}


class AddMembersBody(BaseModel):
    stocks: list[dict]


@router.post("/groups/{group_id}/members")
async def api_add_members(group_id: int, body: AddMembersBody, session: AsyncSession = Depends(db_session)):
    await groups_repo.add_members(session, group_id, body.stocks)
    return {"error": ""}


@router.delete("/groups/{group_id}/members/{code}")
async def api_remove_member(group_id: int, code: str, session: AsyncSession = Depends(db_session)):
    ok = await groups_repo.remove_member(session, group_id, code)
    if not ok:
        raise HTTPException(404, "member not found")
    return {"error": ""}
