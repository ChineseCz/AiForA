"""管理员登录（Phase 3）。此路由不加鉴权守卫（登录本身要开放），但限流更严（防爆破）。"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_admin
from app.core.ratelimit import limiter
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.repositories import admins as admins_repo

router = APIRouter(prefix="/api/admin")


@router.post("/login")
@limiter.limit(settings.rate_limit_login)
async def login(request: Request, session: AsyncSession = Depends(db_session)):
    raw = await request.body()
    try:
        body = json.loads(raw) if raw else {}
    except ValueError:
        body = {}
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    remember = bool(body.get("remember", False))
    if not username or not password:
        return JSONResponse({"error": "请输入用户名和密码"}, status_code=400)

    admin = await admins_repo.get_by_username(session, username)
    if not admin or not verify_password(password, admin["password_hash"]):
        return JSONResponse({"error": "用户名或密码错误"}, status_code=401)

    token = create_access_token(
        username,
        expire_minutes=settings.remember_jwt_expire_minutes if remember else settings.jwt_expire_minutes,
    )
    return {"access_token": token, "token_type": "bearer", "username": username}


@router.get("/me")
async def me(admin: str = Depends(require_admin)):
    """校验当前 token 是否有效（前端判断登录态）。"""
    return {"username": admin}
