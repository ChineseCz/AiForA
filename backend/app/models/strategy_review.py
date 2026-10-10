from sqlalchemy import BigInteger, Date, Double, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StrategyDailyRun(Base):
    __tablename__ = "strategy_daily_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(Date, nullable=False)
    strategy_key: Mapped[str] = mapped_column(String, nullable=False)
    strategy_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pick_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("trade_date", "strategy_key", name="uq_strategy_daily_run"),
        Index("idx_strategy_daily_run_date", "trade_date"),
    )


class StrategyDailyPick(Base):
    __tablename__ = "strategy_daily_picks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    entry_close: Mapped[float | None] = mapped_column(Double)

    __table_args__ = (
        UniqueConstraint("run_id", "code", name="uq_strategy_daily_pick"),
        Index("idx_strategy_daily_pick_run", "run_id"),
        Index("idx_strategy_daily_pick_code", "code"),
    )
