"""job_runs 表（新增）：取代内存里的 crawl_state / *_sync_state 字典 + /status 轮询。

Phase 1 仅建表；Phase 2 由后台任务写入、状态接口读取。
kind: crawl / summarize / stock_sync / stock_backfill / finance_sync / sector_sync / sector_members_sync
status: running / done / error
"""
from sqlalchemy import JSON, BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)     # 手动 / 定时
    log: Mapped[str | None] = mapped_column(Text)           # 换行拼接的日志行
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[int | None] = mapped_column(BigInteger)
    finished_at: Mapped[int | None] = mapped_column(BigInteger)
    progress: Mapped[dict | None] = mapped_column(JSON)
    parameters: Mapped[dict | None] = mapped_column(JSON)
    artifact_path: Mapped[str | None] = mapped_column(Text)
