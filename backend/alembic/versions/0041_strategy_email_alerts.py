"""Add per-combination email alert setting."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "saved_strategy_combinations",
        sa.Column("alerts_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("saved_strategy_combinations", "alerts_enabled")
