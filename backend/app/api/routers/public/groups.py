"""自选分组：只读（列表 + 成员）。写操作留 Phase 2 管理员接口。"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
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
