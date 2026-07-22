"""add user_id to stock_groups

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    # 先删原来的单列唯一约束
    op.drop_constraint("stock_groups_name_key", "stock_groups", type_="unique")
    # 加 user_id 列（nullable，已有管理员全局组保留 NULL）
    op.add_column("stock_groups", sa.Column("user_id", sa.String(100), nullable=True))
    op.create_index("ix_stock_groups_user_id", "stock_groups", ["user_id"])
    # 联合唯一：同一用户内分组名不重复（NULL 用户的全局管理组也受约束，但 PG NULL != NULL）
    op.create_unique_constraint("uq_stock_groups_user_name", "stock_groups", ["user_id", "name"])


def downgrade():
    op.drop_constraint("uq_stock_groups_user_name", "stock_groups", type_="unique")
    op.drop_index("ix_stock_groups_user_id", table_name="stock_groups")
    op.drop_column("stock_groups", "user_id")
    op.create_unique_constraint("stock_groups_name_key", "stock_groups", ["name"])
