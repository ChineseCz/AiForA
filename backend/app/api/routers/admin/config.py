"""管理员：定时配置 + 分组写操作。Phase 2 已接入 schedules / stock_groups 表。"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import cache
from app.core.cache import CacheService
from app.repositories import sync_data as db
from app.services.external import wechat
from app.core.config import settings

router = APIRouter(prefix="/api")


async def _json_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


# ================= 定时配置 =================
@router.get("/schedule")
async def get_schedule():
    return await run_in_threadpool(db.get_schedule)


@router.post("/schedule")
async def set_schedule(request: Request):
    body = await _json_body(request)
    try:
        interval = max(5, int(body.get("interval", 30) or 30))
    except (ValueError, TypeError):
        interval = 30
    cfg = {
        "enabled": bool(body.get("enabled", False)),
        "start": str(body.get("start", "08:00")),
        "end": str(body.get("end", "22:00")),
        "interval": interval,
        "stock_auto_sync_enabled": bool(body.get("stock_auto_sync_enabled", True)),
        "weekly_summary_enabled": bool(body.get("weekly_summary_enabled", True)),
    }
    return await run_in_threadpool(db.save_schedule, cfg)


# ================= 分组写 =================
@router.post("/groups")
async def create_group(request: Request):
    body = await _json_body(request)
    name = (body.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "分组名不能为空"}, status_code=400)
    group_id = await run_in_threadpool(db.create_group, name)
    if group_id is None:
        return JSONResponse({"error": "分组名已存在"}, status_code=400)
    return {"id": group_id, "name": name, "error": ""}


@router.delete("/groups/{group_id}")
async def delete_group(group_id: int):
    await run_in_threadpool(db.delete_group, group_id)
    return {"error": ""}


@router.post("/groups/{group_id}/members")
async def add_group_members(group_id: int, request: Request):
    body = await _json_body(request)
    stocks = [
        {"code": s.get("code"), "name": s.get("name")}
        for s in (body.get("stocks") or []) if s.get("code")
    ]
    if not stocks:
        return JSONResponse({"error": "没有可添加的股票"}, status_code=400)
    n = await run_in_threadpool(db.add_group_members, group_id, stocks)
    return {"added": n, "error": ""}


@router.delete("/groups/{group_id}/members/{code}")
async def remove_group_member(group_id: int, code: str):
    await run_in_threadpool(db.remove_group_member, group_id, code)
    return {"error": ""}


# ================= 访客登录开关（Phase 9） =================
@router.get("/auth-settings")
async def get_auth_settings():
    return await run_in_threadpool(db.get_auth_settings)


@router.post("/auth-settings")
async def set_auth_settings(request: Request):
    body = await _json_body(request)
    cfg = {"require_login_enabled": bool(body.get("require_login_enabled", False))}
    return await run_in_threadpool(db.save_auth_settings, cfg)


# ================= 微信公众号菜单 =================
_WX_TOKEN_REDIS_KEY = "wx:access_token"
_WX_DEFAULT_MENU = {
    "button": [
        {"type": "click", "name": "获取验证码", "key": "GET_CODE"}
    ]
}


@router.post("/wechat/menu")
async def create_wechat_menu(c: CacheService = Depends(cache)):
    """一键创建/更新公众号自定义菜单，管理员调用一次即可。"""
    cached = await c.client.get(_WX_TOKEN_REDIS_KEY)
    if cached:
        token = cached
    else:
        token = await run_in_threadpool(wechat.fetch_access_token, settings.wechat_appid, settings.wechat_appsecret)
        await c.client.set(_WX_TOKEN_REDIS_KEY, token, ex=7000)
    result = await run_in_threadpool(wechat.create_menu, token, _WX_DEFAULT_MENU)
    if result.get("errcode", 0) != 0:
        return JSONResponse({"error": f"微信接口返回: {result}"}, status_code=502)
    return {"error": "", "detail": result}
