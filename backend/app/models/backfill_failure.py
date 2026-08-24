"""历史 K 线回补失败清单。"""
from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BackfillFailure(Base):
    __tablename__ = "backfill_failures"

    asset_type: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, primary_key=True)
    last_job_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
