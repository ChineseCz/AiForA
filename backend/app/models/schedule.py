"""schedules 表（新增）：取代 data/schedule.json。

单行配置（自动采集窗口 + 间隔）。Phase 2 由 Celery beat 读取。
"""
from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    start: Mapped[str] = mapped_column(String, default="08:00")
    end: Mapped[str] = mapped_column(String, default="22:00")
    interval: Mapped[int] = mapped_column(Integer, default=30)   # 分钟
    updated_at: Mapped[int | None] = mapped_column(BigInteger)
