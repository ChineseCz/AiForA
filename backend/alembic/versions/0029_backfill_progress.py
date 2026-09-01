"""Persist per-asset historical K-line backfill progress for resumable jobs."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backfill_progress",
        sa.Column("job_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_type", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("target_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("job_id", "asset_type", "code"),
    )
    op.create_index("idx_backfill_progress_job_status", "backfill_progress", ["job_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_backfill_progress_job_status", table_name="backfill_progress")
    op.drop_table("backfill_progress")
