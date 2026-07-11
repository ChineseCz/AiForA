"""看板总览。"""
import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.services.overview import build_overview, get_board_bullish_heat, get_bullish_heat

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
    data["bullish_heat"], data["bullish_heat_boards"] = await asyncio.gather(
        run_in_threadpool(get_bullish_heat),
        run_in_threadpool(get_board_bullish_heat),
    )
    await c.set_json(key, data, settings.cache_ttl_overview)
    return data
