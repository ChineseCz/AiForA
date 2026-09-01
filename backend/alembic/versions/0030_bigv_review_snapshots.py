"""Persist finalized per-post Big V review results for incremental recalculation."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "bigv_review_snapshots",
        sa.Column("post_id", sa.String(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("finalized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("post_id"),
    )
    op.create_index("idx_bigv_review_snapshots_finalized", "bigv_review_snapshots", ["finalized"])


def downgrade() -> None:
    op.drop_index("idx_bigv_review_snapshots_finalized", table_name="bigv_review_snapshots")
    op.drop_table("bigv_review_snapshots")
