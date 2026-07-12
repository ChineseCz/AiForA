"""users 表加 nickname（微信昵称，Phase 9 补充）

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("nickname", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "nickname")
