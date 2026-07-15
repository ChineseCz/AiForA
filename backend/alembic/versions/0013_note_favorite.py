"""add is_favorite to trade_notes

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("trade_notes", sa.Column("is_favorite", sa.Boolean, nullable=False, server_default="false"))


def downgrade():
    op.drop_column("trade_notes", "is_favorite")
