"""模拟盘资金账户

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("user_id", sa.String(200), primary_key=True),
        sa.Column("balance", sa.Numeric(16, 4), nullable=False, server_default="100000"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("paper_accounts")
