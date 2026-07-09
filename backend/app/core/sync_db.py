"""同步数据库引擎与会话（psycopg）。

仅供 CPU 密集的选股 / K线计算使用：ported stock.py 的逻辑是同步且重
（拉全量历史 + 循环 ~5500×90），用 run_in_threadpool + 同步会话跑，
保持移植逻辑逐字不变。轻量读接口请走 core/db.py 的异步会话。
"""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

sync_engine = create_engine(
    settings.database_url_sync,
    pool_size=settings.sync_db_pool_size,
    max_overflow=settings.sync_db_max_overflow,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle,
)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, class_=Session)


@contextmanager
def sync_session() -> Iterator[Session]:
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()
