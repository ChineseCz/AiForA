"""Add per-URL WeChat import status."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wechat_import_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("post_id", sa.String(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_wechat_import_items_url"),
    )
    op.create_index("idx_wechat_import_items_status", "wechat_import_items", ["status"])


def downgrade() -> None:
    op.drop_index("idx_wechat_import_items_status", table_name="wechat_import_items")
    op.drop_table("wechat_import_items")
