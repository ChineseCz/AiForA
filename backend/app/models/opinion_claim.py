"""Structured claims extracted from an article for later market review."""
from sqlalchemy import BigInteger, Double, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OpinionClaim(Base):
    __tablename__ = "opinion_claims"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str | None] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, nullable=False, default="未定向")
    claim: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Double)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ready")
    error: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (Index("idx_opinion_claims_post", "post_id"),)
