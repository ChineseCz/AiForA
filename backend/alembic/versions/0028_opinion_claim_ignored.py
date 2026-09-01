"""Add an explicit ignore flag for manually reviewed opinion claims."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "opinion_claims",
        sa.Column("ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("opinion_claims", "ignored")
