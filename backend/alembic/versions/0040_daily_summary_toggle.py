"""Add an independent toggle for automatic daily summaries."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("schedules", sa.Column("daily_summary_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))

def downgrade() -> None:
    op.drop_column("schedules", "daily_summary_enabled")
