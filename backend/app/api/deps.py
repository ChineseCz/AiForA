"""FastAPI 依赖：DB 会话、缓存、管理员鉴权。"""
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import CacheService, get_cache
from app.core.db import get_session
from app.core.security import decode_token

_bearer = HTTPBearer(auto_error=False)


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for s in get_session():
        yield s


def cache() -> CacheService:
    return get_cache()


async def require_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """校验 Authorization: Bearer <JWT>；返回管理员用户名（sub）。无效 → 401。"""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要管理员登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(creds.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return str(payload["sub"])
