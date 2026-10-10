"""Store user-defined buy/sell strategy combinations."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "saved_strategy_combinations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("buy_expression", sa.JSON(), nullable=False),
        sa.Column("sell_expression", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
    )
    op.create_index("idx_saved_strategy_combination_user", "saved_strategy_combinations", ["user_id"])

def downgrade() -> None:
    op.drop_table("saved_strategy_combinations")
