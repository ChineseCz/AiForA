"""自选股买卖信号通知去重记录

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-27
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("sent_at", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.UniqueConstraint("user_id", "channel", "event_key", name="uq_notification_event"),
    )
    op.create_index("idx_notification_events_sent_at", "notification_events", ["sent_at"])


def downgrade() -> None:
    op.drop_index("idx_notification_events_sent_at", table_name="notification_events")
    op.drop_table("notification_events")
