"""FastAPI 应用工厂。

Phase 1：公开只读路由（原生 dict 输出，与旧 Flask 逐字节一致）。
Phase 3：管理员登录 + JWT 守卫（admin/ 写接口需 Bearer token）+ slowapi 限流 + 启动引导管理员。
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.deps import require_admin
from app.core import cache as cache_mod
from app.core.bootstrap import bootstrap_admin
from app.core.config import settings
from app.core.ratelimit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_admin()  # admins 表空 + env 配置了账号则自动建号
    yield
    await cache_mod.close()


def create_app() -> FastAPI:
    app = FastAPI(title="雪球大V看板 + A股选股 API", version="0.3.0", lifespan=lifespan)

    # 限流：注册 limiter + 异常处理 + 中间件（默认限额施加到所有路由）
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 公开只读路由（匿名）
    from app.api.routers.public import groups, health, meta, overview, posts, screen, sectors, stocks, summaries
    for mod in (meta, overview, posts, summaries, screen, stocks, sectors, groups, health):
        app.include_router(mod.router, tags=["public"])

    # Prometheus 指标 /metrics（Phase 5 可观测性）
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # 管理员登录（开放，限流更严）
    from app.api.routers.admin import auth as admin_auth
    app.include_router(admin_auth.router, tags=["admin-auth"])

    # 管理员写/触发路由（JWT 守卫）
    from app.api.routers.admin import config as admin_config
    from app.api.routers.admin import jobs as admin_jobs
    for mod in (admin_jobs, admin_config):
        app.include_router(mod.router, tags=["admin"], dependencies=[Depends(require_admin)])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
