"""stock_finance 表：每只股票最新一期财务指标。PK code。"""
from sqlalchemy import BigInteger, Double, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockFinance(Base):
    __tablename__ = "stock_finance"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    report_date: Mapped[str | None] = mapped_column(String)       # 报告期 2026-03-31
    eps: Mapped[float | None] = mapped_column(Double)             # 每股收益
    roe: Mapped[float | None] = mapped_column(Double)            # 加权平均净资产收益率(%)
    net_profit_yoy: Mapped[float | None] = mapped_column(Double)  # 净利润同比(%)
    revenue_yoy: Mapped[float | None] = mapped_column(Double)     # 营收同比(%)
    gross_margin: Mapped[float | None] = mapped_column(Double)    # 销售毛利率(%)
    fetched_at: Mapped[int | None] = mapped_column(BigInteger)
