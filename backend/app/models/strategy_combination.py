from sqlalchemy import BigInteger, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SavedStrategyCombination(Base):
    __tablename__ = "saved_strategy_combinations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    buy_expression: Mapped[dict] = mapped_column(JSON, nullable=False)
    sell_expression: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (Index("idx_saved_strategy_combination_user", "user_id"),)
