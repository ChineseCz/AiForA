"""可转债行情快照

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-21
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bond_daily",
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("close", sa.Double()),
        sa.Column("change_pct", sa.Double()),
        sa.Column("volume", sa.Double()),
        sa.Column("amount", sa.Double()),
        sa.Column("high", sa.Double()),
        sa.Column("low", sa.Double()),
        sa.Column("open", sa.Double()),
        sa.Column("pre_close", sa.Double()),
        sa.Column("stock_code", sa.String()),
        sa.Column("stock_name", sa.String()),
        sa.Column("convert_price", sa.Double()),
        sa.Column("conversion_value", sa.Double()),
        sa.Column("premium_rate", sa.Double()),
        sa.Column("maturity_date", sa.String()),
        sa.Column("rating", sa.String()),
        sa.Column("redeem_status", sa.String()),
        sa.Column("fetched_at", sa.BigInteger()),
        sa.PrimaryKeyConstraint("trade_date", "code"),
    )
    op.create_index("idx_bond_daily_date", "bond_daily", ["trade_date"])
    op.create_index("idx_bond_daily_code", "bond_daily", ["code"])


def downgrade() -> None:
    op.drop_index("idx_bond_daily_code", table_name="bond_daily")
    op.drop_index("idx_bond_daily_date", table_name="bond_daily")
    op.drop_table("bond_daily")
