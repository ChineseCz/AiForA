"""add is_paper flag for paper trading

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("trade_records", sa.Column("is_paper", sa.Boolean(), nullable=False, server_default="false"))

    op.add_column("trade_notes", sa.Column("is_paper", sa.Boolean(), nullable=False, server_default="false"))
    op.drop_constraint("uq_trade_notes_user_date", "trade_notes", type_="unique")
    op.create_unique_constraint(
        "uq_trade_notes_user_date_paper", "trade_notes", ["user_id", "note_date", "is_paper"]
    )

    op.add_column("stock_groups", sa.Column("is_paper", sa.Boolean(), nullable=False, server_default="false"))
    op.drop_constraint("uq_stock_groups_user_name", "stock_groups", type_="unique")
    op.create_unique_constraint(
        "uq_stock_groups_user_name_paper", "stock_groups", ["user_id", "name", "is_paper"]
    )


def downgrade():
    op.drop_constraint("uq_stock_groups_user_name_paper", "stock_groups", type_="unique")
    op.create_unique_constraint("uq_stock_groups_user_name", "stock_groups", ["user_id", "name"])
    op.drop_column("stock_groups", "is_paper")

    op.drop_constraint("uq_trade_notes_user_date_paper", "trade_notes", type_="unique")
    op.create_unique_constraint("uq_trade_notes_user_date", "trade_notes", ["user_id", "note_date"])
    op.drop_column("trade_notes", "is_paper")

    op.drop_column("trade_records", "is_paper")
