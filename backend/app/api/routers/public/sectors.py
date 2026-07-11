"""板块行情聚合榜：GET /api/sectors/rank（纯库内聚合，走同步引擎 + threadpool）。"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import cache
from app.core.cache import CacheService
from app.core.config import settings
from app.services import sector_rank

router = APIRouter(prefix="/api")


@router.get("/sectors/rank")
async def api_sectors_rank(c: CacheService = Depends(cache)):
    key = await c.key("sectors_rank")
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    payload, status = await run_in_threadpool(sector_rank.get_rank)
    if status == 200:
        await c.set_json(key, payload, settings.cache_ttl_sectors)
        return payload
    return JSONResponse(payload, status_code=status)
