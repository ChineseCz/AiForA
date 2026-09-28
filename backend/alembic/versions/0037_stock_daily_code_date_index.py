"""Speed up per-stock chronological strategy backtests."""
from collections.abc import Sequence

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_stock_daily_code_trade_date",
        "stock_daily",
        ["code", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_stock_daily_code_trade_date", table_name="stock_daily")
