"""users 表加 is_admin 字段，管理员权限存库而非靠配置项

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"))
    # 把已注册的管理员邮箱直接标记（未注册时此 UPDATE 是空操作，注册后需手动 SET is_admin=true）
    op.execute("UPDATE users SET is_admin = TRUE WHERE email = '1123093545@qq.com'")


def downgrade() -> None:
    op.drop_column("users", "is_admin")
