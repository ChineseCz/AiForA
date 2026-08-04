"""FastAPI 依赖：DB 会话、缓存、管理员/访客鉴权。"""
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheService, get_cache
from app.core.db import get_session
from app.core.security import decode_token

_bearer = HTTPBearer(auto_error=False)

_VISITOR_MODE_CACHE_KEY = "auth:require_login_enabled"  # 复用同一 Redis key，DB 字段未变
_VISITOR_MODE_CACHE_TTL = 30


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for s in get_session():
        yield s


def cache() -> CacheService:
    return get_cache()


async def _is_visitor_mode_enabled(c: CacheService, db: AsyncSession) -> bool:
    """读 auth_settings.require_login_enabled（语义变更为：访客模式是否开启）。"""
    cached = await c.client.get(_VISITOR_MODE_CACHE_KEY)
    if cached is not None:
        return cached == "1"
    row = (
        await db.execute(text("SELECT require_login_enabled FROM auth_settings ORDER BY id LIMIT 1"))
    ).first()
    enabled = bool(row[0]) if row else True
    await c.client.set(_VISITOR_MODE_CACHE_KEY, "1" if enabled else "0", ex=_VISITOR_MODE_CACHE_TTL)
    return enabled


def _decode_bearer(creds: HTTPAuthorizationCredentials | None) -> dict | None:
    if creds is None or not creds.credentials:
        return None
    return decode_token(creds.credentials)


async def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """校验 Authorization: Bearer <JWT>（typ=admin，或早期无 typ 字段的旧 token）；返回管理员用户名。无效 → 401。"""
    payload = _decode_bearer(creds)
    if not payload or not payload.get("sub") or payload.get("typ", "admin") != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要管理员登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(payload["sub"])


async def require_visitor(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """校验访客 JWT（typ=visitor）；游客(sty=guest)不允许操作个人数据，返回 403。"""
    payload = _decode_bearer(creds)
    if not payload or not payload.get("sub") or payload.get("typ") != "visitor":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("sty") == "guest":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="游客模式不支持此功能，请登录账号")
    return str(payload["sub"])


async def require_visitor_payload(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """校验访客 JWT 并返回完整 payload；游客(sty=guest)不允许操作个人数据，返回 403。"""
    payload = _decode_bearer(creds)
    if not payload or not payload.get("sub") or payload.get("typ") != "visitor":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("sty") == "guest":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="游客模式不支持此功能，请登录账号")
    return payload


async def require_visitor_or_anonymous(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    c: CacheService = Depends(cache),
    db: AsyncSession = Depends(db_session),
) -> str | None:
    """始终要求登录；游客 JWT(sty=guest) 仅在访客模式开启时放行只读请求。"""
    payload = _decode_bearer(creds)
    if not payload or not payload.get("sub") or payload.get("typ", "admin") not in ("admin", "visitor"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("sty") == "guest" and not await _is_visitor_mode_enabled(c, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="访客模式已关闭，请登录账号",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(payload["sub"])
