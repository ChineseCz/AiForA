"""自选股分组：stock_groups + stock_group_members。"""
from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StockGroup(Base):
    __tablename__ = "stock_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[int | None] = mapped_column(BigInteger)
    user_id: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_stock_groups_user_name"),
        Index("ix_stock_groups_user_id", "user_id"),
    )


class StockGroupMember(Base):
    __tablename__ = "stock_group_members"

    # 原表仅 UNIQUE(group_id, code)，用其作复合主键。
    group_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    added_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (Index("idx_group_members_group", "group_id"),)
