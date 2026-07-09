"""看板总览。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.services.overview import build_overview

router = APIRouter(prefix="/api")


@router.get("/overview")
async def api_overview(
    user: str | None = Query(default=None),
    session: AsyncSession = Depends(db_session),
    c: CacheService = Depends(cache),
):
    user_id = user or None
    key = await c.key("overview", user=user_id)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    data = await build_overview(session, user_id)
    await c.set_json(key, data, settings.cache_ttl_overview)
    return data
