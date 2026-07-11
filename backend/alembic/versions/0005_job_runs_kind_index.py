"""job_runs 补索引：(kind, id DESC)，供状态轮询接口按 kind 取最新一条 (Phase 8)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_job_runs_kind_id", "job_runs", ["kind", sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_job_runs_kind_id", table_name="job_runs")
