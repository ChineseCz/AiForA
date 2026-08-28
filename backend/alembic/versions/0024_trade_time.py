"""Store optional execution time for screenshot imports."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trade_records", sa.Column("trade_time", sa.String(8), nullable=True))
    op.create_index("ix_trade_records_dedup", "trade_records", ["user_id", "trade_date", "trade_time", "code"])


def downgrade() -> None:
    op.drop_index("ix_trade_records_dedup", table_name="trade_records")
    op.drop_column("trade_records", "trade_time")
