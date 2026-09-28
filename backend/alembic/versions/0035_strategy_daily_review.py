"""Store daily strategy picks for performance review."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_daily_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("strategy_key", sa.String(), nullable=False),
        sa.Column("strategy_params", sa.JSON(), nullable=False),
        sa.Column("pick_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint("trade_date", "strategy_key", name="uq_strategy_daily_run"),
    )
    op.create_index("idx_strategy_daily_run_date", "strategy_daily_runs", ["trade_date"])
    op.create_table(
        "strategy_daily_picks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("entry_close", sa.Double(), nullable=True),
        sa.UniqueConstraint("run_id", "code", name="uq_strategy_daily_pick"),
    )
    op.create_index("idx_strategy_daily_pick_run", "strategy_daily_picks", ["run_id"])
    op.create_index("idx_strategy_daily_pick_code", "strategy_daily_picks", ["code"])


def downgrade() -> None:
    op.drop_table("strategy_daily_picks")
    op.drop_table("strategy_daily_runs")
