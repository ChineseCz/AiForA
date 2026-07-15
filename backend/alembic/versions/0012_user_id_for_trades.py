"""add user_id to trade_records and trade_notes

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("trade_records", sa.Column("user_id", sa.String(100), nullable=True))
    op.create_index("ix_trade_records_user_id", "trade_records", ["user_id"])

    # trade_notes: 原来 note_date 唯一约束改为 (user_id, note_date) 联合唯一
    op.drop_index("ix_trade_notes_note_date", table_name="trade_notes")
    op.drop_constraint("trade_notes_note_date_key", "trade_notes", type_="unique")
    op.add_column("trade_notes", sa.Column("user_id", sa.String(100), nullable=True))
    op.create_unique_constraint("uq_trade_notes_user_date", "trade_notes", ["user_id", "note_date"])
    op.create_index("ix_trade_notes_user_id", "trade_notes", ["user_id"])


def downgrade():
    op.drop_index("ix_trade_notes_user_id", table_name="trade_notes")
    op.drop_constraint("uq_trade_notes_user_date", "trade_notes", type_="unique")
    op.drop_column("trade_notes", "user_id")
    op.create_unique_constraint("trade_notes_note_date_key", "trade_notes", ["note_date"])
    op.create_index("ix_trade_notes_note_date", "trade_notes", ["note_date"])

    op.drop_index("ix_trade_records_user_id", table_name="trade_records")
    op.drop_column("trade_records", "user_id")
