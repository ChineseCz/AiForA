"""trade_notes

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "trade_notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("note_date", sa.Date, nullable=False, unique=True),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.BigInteger, nullable=False),
    )
    op.create_index("ix_trade_notes_note_date", "trade_notes", ["note_date"])


def downgrade():
    op.drop_table("trade_notes")
