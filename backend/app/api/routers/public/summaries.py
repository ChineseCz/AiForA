"""总结查看：周期 key 列表 + 单份总结（markdown 渲染）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.core.markdown import render_md
from app.repositories import summaries as sum_repo

router = APIRouter(prefix="/api")

PERIOD_TYPES = ("daily", "weekly", "monthly", "yearly", "highlights")


@router.get("/summary_keys")
async def api_summary_keys(
    user: str = Query(default=""),
    type: str = Query(default="daily"),
    session: AsyncSession = Depends(db_session),
    c: CacheService = Depends(cache),
):
    if not user or type not in PERIOD_TYPES:
        return []
    key = await c.key("summary_keys", user=user, type=type)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    data = await sum_repo.get_summary_keys(session, user, type)
    await c.set_json(key, data, settings.cache_ttl_summary_keys)
    return data


@router.get("/summary")
async def api_summary(
    user: str = Query(default=""),
    type: str = Query(default="daily"),
    key: str = Query(default=""),
    session: AsyncSession = Depends(db_session),
    c: CacheService = Depends(cache),
):
    ckey = await c.key("summary", user=user, type=type, key=key)
    hit = await c.get_json(ckey)
    if hit is not None:
        return hit
    content = await sum_repo.get_summary(session, user, type, key)
    if content is None:
        result = {"found": False, "html": ""}
    else:
        result = {"found": True, "html": render_md(content), "raw": content}
    await c.set_json(ckey, result, settings.cache_ttl_summary)
    return result
