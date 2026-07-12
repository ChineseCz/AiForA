"""账号系统（Phase 9）：users 表（手机号+验证码登录）+ auth_settings 表（登录/匿名模式开关）

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-12
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(), nullable=True, unique=True),
        sa.Column("openid", sa.String(), nullable=True, unique=True),
        sa.Column("created_at", sa.BigInteger(), nullable=True),
    )
    op.create_table(
        "auth_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("require_login_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("auth_settings")
    op.drop_table("users")
