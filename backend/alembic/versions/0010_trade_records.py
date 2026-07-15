"""trade_records 操作复盘记录表

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trade_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("stock_name", sa.String(), nullable=True),
        sa.Column("direction", sa.String(), nullable=False),  # buy | sell
        sa.Column("price", sa.Numeric(12, 4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("trade_date", sa.String(10), nullable=False),  # YYYY-MM-DD
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_trade_records_code", "trade_records", ["code"])
    op.create_index("ix_trade_records_date", "trade_records", ["trade_date"])


def downgrade() -> None:
    op.drop_index("ix_trade_records_date", "trade_records")
    op.drop_index("ix_trade_records_code", "trade_records")
    op.drop_table("trade_records")
