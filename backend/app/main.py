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

from app.api.deps import require_admin, require_visitor_or_anonymous
from app.core import cache as cache_mod
from app.core.bootstrap import bootstrap_admin
from app.core.config import settings
from app.core.ratelimit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_admin()  # admins 表空 + env 配置了账号则自动建号
    await _cleanup_zombie_jobs()
    yield
    await cache_mod.close()


async def _cleanup_zombie_jobs():
    """清理上次崩溃留下的僵尸任务（status=running 但 worker 已不在）。"""
    import time
    from sqlalchemy import text
    from app.core.db import async_session_maker
    async with async_session_maker() as s:
        result = await s.execute(text(
            "UPDATE job_runs SET status='error', finished_at=:now, error='worker重启，任务中断' "
            "WHERE status='running'"
        ), {"now": int(time.time())})
        await s.commit()
        if result.rowcount:
            print(f"🧹 清理僵尸任务 {result.rowcount} 条")


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
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # 访客账号系统（注册/登录，开放，限流更严）+ 匿名访问开关查询接口（开放）
    from app.api.routers.public import user_auth
    app.include_router(user_auth.router, tags=["user-auth"])
    app.include_router(user_auth.auth_config_router, tags=["user-auth"])

    # 公开只读路由（登录/纯匿名开关由 require_visitor_or_anonymous 决定是否需要鉴权）
    from app.api.routers.public import groups, health, meta, overview, posts, screen, sectors, settings as pub_settings, stocks, summaries, trades, notes
    for mod in (meta, overview, posts, summaries, screen, stocks, sectors, groups, trades, notes, pub_settings):
        app.include_router(mod.router, tags=["public"], dependencies=[Depends(require_visitor_or_anonymous)])

    # 健康检查（容器编排探针，始终开放）
    app.include_router(health.router, tags=["public"])

    # Prometheus 指标 /metrics（Phase 5 可观测性）
    # 不使用 .expose() 的默认无守卫路由，改为手动注册并加管理员鉴权，防止内部指标被公网探测
    from prometheus_fastapi_instrumentator import Instrumentator
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    from fastapi.responses import Response as FastAPIResponse

    instrumentator = Instrumentator()
    instrumentator.instrument(app)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(_admin: str = Depends(require_admin)):
        return FastAPIResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

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
