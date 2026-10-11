"""Add configurable Xueqiu crawl lookback days."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("crawl_days", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("schedules", "crawl_days")
