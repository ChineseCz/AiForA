"""Persist parameters for repeatable and auditable jobs."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("job_runs", sa.Column("parameters", sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column("job_runs", "parameters")
