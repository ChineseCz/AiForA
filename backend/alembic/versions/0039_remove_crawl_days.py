"""Remove obsolete Xueqiu crawl lookback configuration."""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.drop_column("schedules", "crawl_days")

def downgrade() -> None:
    op.add_column("schedules", sa.Column("crawl_days", sa.Integer(), nullable=False, server_default="0"))
