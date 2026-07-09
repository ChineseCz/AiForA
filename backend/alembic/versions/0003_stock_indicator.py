"""stock_indicator precompute table (Phase 5)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_indicator",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("trade_date", sa.String()),
        sa.Column("ma5", sa.Double()),
        sa.Column("ma10", sa.Double()),
        sa.Column("ma20", sa.Double()),
        sa.Column("cross1", sa.Boolean(), server_default=sa.false()),
        sa.Column("cross23", sa.Boolean(), server_default=sa.false()),
        sa.Column("rise5", sa.Boolean(), server_default=sa.false()),
        sa.Column("price_above20", sa.Boolean(), server_default=sa.false()),
        sa.Column("duotou", sa.Boolean(), server_default=sa.false()),
        sa.Column("macd_recent", sa.Boolean(), server_default=sa.false()),
        sa.Column("kdj_recent", sa.Boolean(), server_default=sa.false()),
        sa.Column("updated_at", sa.BigInteger()),
    )


def downgrade() -> None:
    op.drop_table("stock_indicator")
