"""Persist completed strategy backtests for exact-request reuse."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_backtest_cache",
        sa.Column("cache_key", sa.String(length=64), primary_key=True),
        sa.Column("data_signature", sa.String(length=128), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("strategy_backtest_cache")
