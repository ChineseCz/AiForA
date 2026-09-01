"""Add historical index bars for benchmark review."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "index_daily",
        sa.Column("trade_date", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("open", sa.Double(), nullable=True),
        sa.Column("high", sa.Double(), nullable=True),
        sa.Column("low", sa.Double(), nullable=True),
        sa.Column("close", sa.Double(), nullable=True),
        sa.Column("volume", sa.Double(), nullable=True),
        sa.Column("fetched_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("trade_date", "code"),
    )
    op.create_index("idx_index_daily_code_date", "index_daily", ["code", "trade_date"])


def downgrade() -> None:
    op.drop_index("idx_index_daily_code_date", table_name="index_daily")
    op.drop_table("index_daily")
