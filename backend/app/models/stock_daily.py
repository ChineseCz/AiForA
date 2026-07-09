"""stock_daily 表：行情快照 + 历史K线合流。5.2M+ 行。

原 SQLite 表无显式主键、仅 UNIQUE(trade_date, code)。这里用 (trade_date, code) 作复合主键
（即那条自然键），避免在 5.2M 行上多挂一个自增序列；upsert 冲突目标也用它。
"""
from sqlalchemy import BigInteger, Double, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockDaily(Base):
    __tablename__ = "stock_daily"

    trade_date: Mapped[str] = mapped_column(String, primary_key=True)   # YYYY-MM-DD
    code: Mapped[str] = mapped_column(String, primary_key=True)         # 6位代码
    name: Mapped[str | None] = mapped_column(String)
    close: Mapped[float | None] = mapped_column(Double)
    change_pct: Mapped[float | None] = mapped_column(Double)
    volume: Mapped[float | None] = mapped_column(Double)
    amount: Mapped[float | None] = mapped_column(Double)
    turnover_rate: Mapped[float | None] = mapped_column(Double)
    volume_ratio: Mapped[float | None] = mapped_column(Double)
    pe_ttm: Mapped[float | None] = mapped_column(Double)
    pb: Mapped[float | None] = mapped_column(Double)
    total_mv: Mapped[float | None] = mapped_column(Double)
    circ_mv: Mapped[float | None] = mapped_column(Double)
    high: Mapped[float | None] = mapped_column(Double)
    low: Mapped[float | None] = mapped_column(Double)
    open: Mapped[float | None] = mapped_column(Double)
    pre_close: Mapped[float | None] = mapped_column(Double)
    fetched_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        Index("idx_stock_daily_date", "trade_date"),
        Index("idx_stock_daily_code", "code"),  # 个股详情页按 code 取全量历史
    )
