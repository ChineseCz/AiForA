"""Add in-app notification content and read state.

Revision ID: 0023
Revises: 0022
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notification_events", sa.Column("title", sa.String(200), nullable=True))
    op.add_column("notification_events", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("notification_events", sa.Column("read_at", sa.BigInteger(), nullable=True))
    op.create_index("idx_notification_events_user_read", "notification_events", ["user_id", "read_at"])


def downgrade() -> None:
    op.drop_index("idx_notification_events_user_read", table_name="notification_events")
    op.drop_column("notification_events", "read_at")
    op.drop_column("notification_events", "content")
    op.drop_column("notification_events", "title")
