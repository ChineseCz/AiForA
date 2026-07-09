"""异步数据库引擎与会话（asyncpg）。轻量读接口走这里。"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle,
    connect_args={
        # 每个连接设 statement_timeout，防止慢查询拖垮事件循环。
        "server_settings": {"statement_timeout": str(settings.db_statement_timeout_ms)},
        # statement_cache_size=0：关闭 asyncpg 预处理语句缓存，使其可安全经 PgBouncer
        # 事务级连接池（否则预处理语句会在复用的服务端连接上冲突）。直连 PG 时开销可忽略。
        "statement_cache_size": 0,
    },
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：产出一个异步会话。"""
    async with async_session_maker() as session:
        yield session
