"""schedules 表新增两个开关字段：全市场行情10分钟同步、周三/周日周总结 (Phase 6)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedules",
        sa.Column("stock_auto_sync_enabled", sa.Boolean(), server_default=sa.true()),
    )
    op.add_column(
        "schedules",
        sa.Column("weekly_summary_enabled", sa.Boolean(), server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("schedules", "weekly_summary_enabled")
    op.drop_column("schedules", "stock_auto_sync_enabled")
