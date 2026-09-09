"""Add public national team holding snapshots."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "national_team_holdings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("report_date", sa.String(), nullable=False),
        sa.Column("institution", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("shares", sa.Double(), nullable=True),
        sa.Column("holding_ratio", sa.Double(), nullable=True),
        sa.Column("change_shares", sa.Double(), nullable=True),
        sa.Column("change_type", sa.String(), nullable=True),
        sa.Column("market_value", sa.Double(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("updated_at", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("report_date", "institution", "code", name="uq_national_team_holding"),
    )
    op.create_index("idx_national_team_report", "national_team_holdings", ["report_date"])
    op.create_index("idx_national_team_institution", "national_team_holdings", ["institution"])
    op.create_index("idx_national_team_code", "national_team_holdings", ["code"])


def downgrade() -> None:
    op.drop_table("national_team_holdings")
