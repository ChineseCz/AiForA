"""Per-URL status for public-account article imports."""
from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WechatImportItem(Base):
    __tablename__ = "wechat_import_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    post_id: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (Index("idx_wechat_import_items_status", "status"),)
