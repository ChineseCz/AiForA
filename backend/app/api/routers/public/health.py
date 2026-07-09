"""健康与就绪探针（Phase 5）。

/health  —— 存活探针（进程在跑即 200，已在 main.py 定义，这里补 /ready）。
/ready   —— 就绪探针：真正查一次 Postgres + Redis，任一不可达则 503（供 LB / K8s readiness 用）。
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService

router = APIRouter()


@router.get("/ready")
async def ready(session: AsyncSession = Depends(db_session), c: CacheService = Depends(cache)):
    checks = {"postgres": False, "redis": False}
    try:
        await session.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        pass
    try:
        await c.client.ping()
        checks["redis"] = True
    except Exception:
        pass
    ok = all(checks.values())
    return JSONResponse({"ready": ok, "checks": checks}, status_code=200 if ok else 503)
