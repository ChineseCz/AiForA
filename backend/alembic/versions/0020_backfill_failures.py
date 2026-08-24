"""历史 K 线回补失败清单

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backfill_failures",
        sa.Column("asset_type", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("last_job_id", sa.BigInteger()),
        sa.Column("error", sa.Text()),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("asset_type", "code"),
    )
    op.create_index("idx_backfill_failures_updated", "backfill_failures", ["updated_at"])


def downgrade() -> None:
    op.drop_index("idx_backfill_failures_updated", table_name="backfill_failures")
    op.drop_table("backfill_failures")
