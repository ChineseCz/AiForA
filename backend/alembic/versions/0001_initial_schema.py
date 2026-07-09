"""initial schema —— 镜像旧 SQLite 8 张表 + 3 张新管理表

Revision ID: 0001
Revises:
Create Date: 2026-07-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ===== posts =====
    op.create_table(
        "posts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String()),
        sa.Column("user_name", sa.String()),
        sa.Column("created_at", sa.BigInteger()),
        sa.Column("date", sa.String()),
        sa.Column("text", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("url", sa.String()),
        sa.Column("like_count", sa.Integer(), server_default="0"),
        sa.Column("retweet_count", sa.Integer(), server_default="0"),
        sa.Column("reply_count", sa.Integer(), server_default="0"),
        sa.Column("fav_count", sa.Integer(), server_default="0"),
        sa.Column("raw_json", sa.Text()),
        sa.Column("images", sa.Text()),
        sa.Column("image_desc", sa.Text()),
        sa.Column("fetched_at", sa.BigInteger()),
    )
    op.create_index("idx_posts_user_date", "posts", ["user_id", "date"])

    # ===== summaries =====
    op.create_table(
        "summaries",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text()),
        sa.Column("period_type", sa.Text()),
        sa.Column("period_key", sa.Text()),
        sa.Column("content", sa.Text()),
        sa.Column("created_at", sa.BigInteger()),
        sa.UniqueConstraint("user_id", "period_type", "period_key", name="uq_summaries_user_type_key"),
    )

    # ===== stock_daily （复合主键 trade_date+code）=====
    op.create_table(
        "stock_daily",
        sa.Column("trade_date", sa.String(), primary_key=True),
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name", sa.String()),
        sa.Column("close", sa.Double()),
        sa.Column("change_pct", sa.Double()),
        sa.Column("volume", sa.Double()),
        sa.Column("amount", sa.Double()),
        sa.Column("turnover_rate", sa.Double()),
        sa.Column("volume_ratio", sa.Double()),
        sa.Column("pe_ttm", sa.Double()),
        sa.Column("pb", sa.Double()),
        sa.Column("total_mv", sa.Double()),
        sa.Column("circ_mv", sa.Double()),
        sa.Column("high", sa.Double()),
        sa.Column("low", sa.Double()),
        sa.Column("open", sa.Double()),
        sa.Column("pre_close", sa.Double()),
        sa.Column("fetched_at", sa.BigInteger()),
    )
    # 迁移脚本会在 COPY 前 drop 掉这两个索引、载完重建；这里先建好以便小数据/常规使用。
    op.create_index("idx_stock_daily_date", "stock_daily", ["trade_date"])
    op.create_index("idx_stock_daily_code", "stock_daily", ["code"])

    # ===== stock_finance =====
    op.create_table(
        "stock_finance",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name", sa.String()),
        sa.Column("report_date", sa.String()),
        sa.Column("eps", sa.Double()),
        sa.Column("roe", sa.Double()),
        sa.Column("net_profit_yoy", sa.Double()),
        sa.Column("revenue_yoy", sa.Double()),
        sa.Column("gross_margin", sa.Double()),
        sa.Column("fetched_at", sa.BigInteger()),
    )

    # ===== stock_groups / stock_group_members =====
    op.create_table(
        "stock_groups",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), unique=True),
        sa.Column("created_at", sa.BigInteger()),
    )
    op.create_table(
        "stock_group_members",
        sa.Column("group_id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("name", sa.String()),
        sa.Column("added_at", sa.BigInteger()),
    )
    op.create_index("idx_group_members_group", "stock_group_members", ["group_id"])

    # ===== sector_catalog / stock_sector =====
    op.create_table(
        "sector_catalog",
        sa.Column("board_code", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), unique=True),
        sa.Column("kind", sa.String()),
        sa.Column("updated_at", sa.BigInteger()),
    )
    op.create_table(
        "stock_sector",
        sa.Column("code", sa.String(), primary_key=True),
        sa.Column("sector", sa.String(), primary_key=True),
        sa.Column("board_code", sa.String()),
        sa.Column("updated_at", sa.BigInteger()),
    )
    op.create_index("idx_stock_sector_sector", "stock_sector", ["sector"])
    op.create_index("idx_stock_sector_code", "stock_sector", ["code"])

    # ===== 新增：xueqiu_users / schedules / job_runs =====
    op.create_table(
        "xueqiu_users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), unique=True),
        sa.Column("name", sa.String()),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true()),
        sa.Column("added_at", sa.BigInteger()),
    )
    op.create_table(
        "schedules",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false()),
        sa.Column("start", sa.String(), server_default="08:00"),
        sa.Column("end", sa.String(), server_default="22:00"),
        sa.Column("interval", sa.Integer(), server_default="30"),
        sa.Column("updated_at", sa.BigInteger()),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String()),
        sa.Column("status", sa.String()),
        sa.Column("source", sa.String()),
        sa.Column("log", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.BigInteger()),
        sa.Column("finished_at", sa.BigInteger()),
    )


def downgrade() -> None:
    for t in (
        "job_runs", "schedules", "xueqiu_users",
        "stock_sector", "sector_catalog",
        "stock_group_members", "stock_groups",
        "stock_finance", "stock_daily", "summaries", "posts",
    ):
        op.drop_table(t)
