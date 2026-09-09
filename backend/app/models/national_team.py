"""公开披露的国家队/重要机构持仓快照。"""
from sqlalchemy import BigInteger, Double, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NationalTeamHolding(Base):
    __tablename__ = "national_team_holdings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_date: Mapped[str] = mapped_column(String, nullable=False)
    institution: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    shares: Mapped[float | None] = mapped_column(Double)
    holding_ratio: Mapped[float | None] = mapped_column(Double)
    change_shares: Mapped[float | None] = mapped_column(Double)
    change_type: Mapped[str | None] = mapped_column(String)
    market_value: Mapped[float | None] = mapped_column(Double)
    source: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("report_date", "institution", "code", name="uq_national_team_holding"),
        Index("idx_national_team_report", "report_date"),
        Index("idx_national_team_institution", "institution"),
        Index("idx_national_team_code", "code"),
    )
