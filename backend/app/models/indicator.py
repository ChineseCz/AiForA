"""stock_indicator 表（Phase 5）：每只股票在最新交易日的预计算技术指标/信号标志。

用途：把选股策略里"拉全量历史 + 循环 5500×90"的现算，改为数据更新后由 worker 预计算一次、
落到本表；选股请求只需读本表 + join 最新快照，消除全表扫描。
"""
from sqlalchemy import BigInteger, Boolean, Double, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockIndicator(Base):
    __tablename__ = "stock_indicator"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    trade_date: Mapped[str | None] = mapped_column(String)  # 计算所依据的最新交易日
    ma5: Mapped[float | None] = mapped_column(Double)
    ma10: Mapped[float | None] = mapped_column(Double)
    ma20: Mapped[float | None] = mapped_column(Double)
    # 均线金叉类标志（对应 ma_cross_metrics）
    cross1: Mapped[bool] = mapped_column(Boolean, default=False)         # MA5/10 3日内金叉
    cross23: Mapped[bool] = mapped_column(Boolean, default=False)        # MA10/20 或 MA5/20 3日内金叉
    rise5: Mapped[bool] = mapped_column(Boolean, default=False)          # 近5日涨幅>3%
    price_above20: Mapped[bool] = mapped_column(Boolean, default=False)  # 收盘价>MA20
    duotou: Mapped[bool] = mapped_column(Boolean, default=False)         # MA5>MA10>MA20 多头排列
    # MACD/KDJ 金叉类标志（对应 golden_cross_metrics）
    macd_recent: Mapped[bool] = mapped_column(Boolean, default=False)
    kdj_recent: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[int | None] = mapped_column(BigInteger)
