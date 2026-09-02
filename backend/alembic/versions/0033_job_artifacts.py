"""Store generated artifact paths for background exports."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("job_runs", sa.Column("artifact_path", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("job_runs", "artifact_path")
