"""Daily historical bars for market indexes used as backtest benchmarks."""
from sqlalchemy import BigInteger, Double, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IndexDaily(Base):
    __tablename__ = "index_daily"

    trade_date: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    open: Mapped[float | None] = mapped_column(Double)
    high: Mapped[float | None] = mapped_column(Double)
    low: Mapped[float | None] = mapped_column(Double)
    close: Mapped[float | None] = mapped_column(Double)
    volume: Mapped[float | None] = mapped_column(Double)
    fetched_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (Index("idx_index_daily_code_date", "code", "trade_date"),)
