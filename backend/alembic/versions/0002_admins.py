"""admins table (Phase 3)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-09
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(), unique=True),
        sa.Column("password_hash", sa.String()),
        sa.Column("created_at", sa.BigInteger()),
    )


def downgrade() -> None:
    op.drop_table("admins")
