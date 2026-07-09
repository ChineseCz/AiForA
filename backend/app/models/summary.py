"""summaries 表：各周期 AI 总结缓存。UNIQUE(user_id, period_type, period_key)。"""
from sqlalchemy import BigInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(Text)
    period_type: Mapped[str | None] = mapped_column(Text)   # daily/weekly/monthly/yearly/highlights
    period_key: Mapped[str | None] = mapped_column(Text)    # 2026-06-30 / 2026-W26 / 2026-06 / 2026
    content: Mapped[str | None] = mapped_column(Text)        # markdown 正文
    created_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("user_id", "period_type", "period_key", name="uq_summaries_user_type_key"),
    )
