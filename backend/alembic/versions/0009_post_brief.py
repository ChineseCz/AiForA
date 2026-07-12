"""posts 表加 brief（抓取时自动生成的一句话总结，供帖子流长文默认收起用）

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("brief", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("posts", "brief")
