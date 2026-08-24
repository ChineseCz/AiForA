"""可转债每日行情及基础估值字段。"""
from sqlalchemy import BigInteger, Double, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BondDaily(Base):
    __tablename__ = "bond_daily"

    trade_date: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    close: Mapped[float | None] = mapped_column(Double)
    change_pct: Mapped[float | None] = mapped_column(Double)
    volume: Mapped[float | None] = mapped_column(Double)
    amount: Mapped[float | None] = mapped_column(Double)
    high: Mapped[float | None] = mapped_column(Double)
    low: Mapped[float | None] = mapped_column(Double)
    open: Mapped[float | None] = mapped_column(Double)
    pre_close: Mapped[float | None] = mapped_column(Double)
    stock_code: Mapped[str | None] = mapped_column(String)
    stock_name: Mapped[str | None] = mapped_column(String)
    convert_price: Mapped[float | None] = mapped_column(Double)
    conversion_value: Mapped[float | None] = mapped_column(Double)
    premium_rate: Mapped[float | None] = mapped_column(Double)
    maturity_date: Mapped[str | None] = mapped_column(String)
    rating: Mapped[str | None] = mapped_column(String)
    redeem_status: Mapped[str | None] = mapped_column(String)
    fetched_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        Index("idx_bond_daily_date", "trade_date"),
        Index("idx_bond_daily_code", "code"),
    )
