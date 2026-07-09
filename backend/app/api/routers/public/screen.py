"""选股筛选（POST，纯计算无写库 → 归入公开只读）。重计算跑 threadpool + 同步会话。"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import cache
from app.core.cache import CacheService
from app.core.config import settings
from app.services import screen_api

router = APIRouter(prefix="/api")


async def _json_body(request: Request) -> dict:
    """安全读取 JSON body（对应旧 Flask get_json(silent=True) or {}）。"""
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


@router.post("/screen")
async def api_screen(request: Request, c: CacheService = Depends(cache)):
    body = await _json_body(request)
    key = await c.key("screen", body=body)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    payload, status = await run_in_threadpool(screen_api.screen, body)
    if status == 200:
        await c.set_json(key, payload, settings.cache_ttl_screen)
        return payload
    return JSONResponse(payload, status_code=status)


@router.post("/screen/preset")
async def api_screen_preset(request: Request, c: CacheService = Depends(cache)):
    body = await _json_body(request)
    key = await c.key("screen_preset", body=body)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    payload, status = await run_in_threadpool(screen_api.preset, body)
    if status == 200:
        await c.set_json(key, payload, settings.cache_ttl_screen)
        return payload
    return JSONResponse(payload, status_code=status)
