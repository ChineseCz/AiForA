"""SQLite → Postgres 一次性数据迁移。

前置：先 `alembic upgrade head` 建好空表。本脚本只搬数据。

用法：
    python -m scripts.migrate_sqlite_to_pg --sqlite ../data/posts.db --truncate

要点：
- stock_daily（5.2M+ 行）用 psycopg3 流式 COPY，fetchmany 分批，绝不整表进内存；
  COPY 前 drop 掉两个索引、载完重建（显著提速）。
- 小表也走 COPY（简单统一）。
- --truncate 幂等：先 TRUNCATE ... RESTART IDENTITY；默认拒绝写入非空表。
- 保留 stock_groups.id / summaries.id（前者被 members.group_id 引用），载完 setval 修正序列。
- seed 新表：xueqiu_users ← 源 .env 的 XUEQIU_USERS；schedules ← data/schedule.json。
"""
import argparse
import json
import os
import sqlite3
import sys
import time

# Windows 控制台默认 GBK，打印 emoji/中文会崩，统一切 UTF-8（同旧 main.py）。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import psycopg

from app.core.config import settings

# 每张表的列顺序（与旧 SQLite SCHEMA 一致）。SELECT 显式列以保证顺序。
TABLE_COLUMNS: dict[str, list[str]] = {
    "posts": [
        "id", "user_id", "user_name", "created_at", "date", "text", "title", "url",
        "like_count", "retweet_count", "reply_count", "fav_count", "raw_json",
        "images", "image_desc", "fetched_at",
    ],
    "summaries": ["id", "user_id", "period_type", "period_key", "content", "created_at"],
    "stock_daily": [
        "trade_date", "code", "name", "close", "change_pct", "volume", "amount",
        "turnover_rate", "volume_ratio", "pe_ttm", "pb", "total_mv", "circ_mv",
        "high", "low", "open", "pre_close", "fetched_at",
    ],
    "stock_finance": [
        "code", "name", "report_date", "eps", "roe", "net_profit_yoy",
        "revenue_yoy", "gross_margin", "fetched_at",
    ],
    "stock_groups": ["id", "name", "created_at"],
    "stock_group_members": ["group_id", "code", "name", "added_at"],
    "sector_catalog": ["board_code", "name", "kind", "updated_at"],
    "stock_sector": ["code", "sector", "board_code", "updated_at"],
}

# 迁移顺序：无外键约束，顺序自由；stock_daily 放最后（最大）。
TABLE_ORDER = [
    "posts", "summaries", "stock_finance", "stock_groups", "stock_group_members",
    "sector_catalog", "stock_sector", "stock_daily",
]

STOCK_DAILY_INDEXES = {
    "idx_stock_daily_date": '("trade_date")',
    "idx_stock_daily_code": '("code")',
}

BATCH = 50_000


def pg_conninfo() -> str:
    """把 SQLAlchemy 的 database_url 转成 psycopg 的 conninfo。"""
    return settings.database_url.replace("+asyncpg", "").replace("+psycopg", "")


def _quote_cols(cols: list[str]) -> str:
    return ", ".join(f'"{c}"' for c in cols)


def table_count(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return cur.fetchone()[0]


def copy_table(sqlite_conn: sqlite3.Connection, pg: psycopg.Connection, table: str) -> int:
    cols = TABLE_COLUMNS[table]
    col_sql = _quote_cols(cols)
    src = sqlite_conn.execute(f"SELECT {', '.join(cols)} FROM {table}")
    n = 0
    with pg.cursor() as pcur:
        with pcur.copy(f'COPY {table} ({col_sql}) FROM STDIN') as cp:
            while True:
                batch = src.fetchmany(BATCH)
                if not batch:
                    break
                for row in batch:
                    cp.write_row(tuple(row))
                n += len(batch)
                if table == "stock_daily":
                    print(f"  … {table}: {n} 行 …", flush=True)
    pg.commit()
    return n


def ensure_empty_or_truncate(pg: psycopg.Connection, truncate: bool) -> None:
    with pg.cursor() as cur:
        if truncate:
            tables = ", ".join(TABLE_ORDER + ["xueqiu_users", "schedules", "job_runs"])
            cur.execute(f"TRUNCATE {tables} RESTART IDENTITY")
            pg.commit()
            print("已 TRUNCATE 全部目标表。")
            return
        for t in TABLE_ORDER:
            if table_count(cur, t) > 0:
                sys.exit(f"❌ 目标表 {t} 非空。加 --truncate 覆盖，或先清空。")


def drop_stock_daily_indexes(pg: psycopg.Connection) -> None:
    with pg.cursor() as cur:
        for name in STOCK_DAILY_INDEXES:
            cur.execute(f"DROP INDEX IF EXISTS {name}")
    pg.commit()
    print("已临时 drop stock_daily 索引（载完重建）。")


def rebuild_stock_daily_indexes(pg: psycopg.Connection) -> None:
    with pg.cursor() as cur:
        for name, cols in STOCK_DAILY_INDEXES.items():
            cur.execute(f"CREATE INDEX IF NOT EXISTS {name} ON stock_daily {cols}")
    pg.commit()
    print("已重建 stock_daily 索引。")


def fix_sequences(pg: psycopg.Connection) -> None:
    """载入保留了显式 id 的表后，把自增序列推到 MAX(id)，避免后续插入撞键。"""
    with pg.cursor() as cur:
        for table in ("summaries", "stock_groups"):
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
            )
    pg.commit()
    print("已修正 summaries / stock_groups 序列。")


def _parse_users(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def read_xueqiu_users(source_env: str) -> list[str]:
    """从环境变量或源 .env 读 XUEQIU_USERS。"""
    if os.getenv("XUEQIU_USERS"):
        return _parse_users(os.getenv("XUEQIU_USERS", ""))
    if os.path.exists(source_env):
        for line in open(source_env, encoding="utf-8"):
            line = line.strip()
            if line.startswith("XUEQIU_USERS="):
                return _parse_users(line.split("=", 1)[1])
    return []


def seed_xueqiu_users(pg: psycopg.Connection, users: list[str]) -> int:
    if not users:
        return 0
    now = int(time.time())
    with pg.cursor() as cur:
        for u in users:
            cur.execute(
                "INSERT INTO xueqiu_users (user_id, name, enabled, added_at) "
                "VALUES (%s, %s, TRUE, %s) ON CONFLICT (user_id) DO NOTHING",
                (u, None, now),
            )
    pg.commit()
    return len(users)


def seed_schedule(pg: psycopg.Connection, data_dir: str) -> None:
    path = os.path.join(data_dir, "schedule.json")
    cfg = {"enabled": False, "start": "08:00", "end": "22:00", "interval": 30}
    if os.path.exists(path):
        try:
            raw = json.load(open(path, encoding="utf-8"))
            cfg["enabled"] = bool(raw.get("enabled", False))
            cfg["start"] = str(raw.get("start", raw.get("time", "08:00")))
            cfg["end"] = str(raw.get("end", "22:00"))
            cfg["interval"] = max(5, int(raw.get("interval", 30)))
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 读取 schedule.json 失败，用默认：{e}")
    now = int(time.time())
    with pg.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM schedules")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO schedules (enabled, start, \"end\", interval, updated_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (cfg["enabled"], cfg["start"], cfg["end"], cfg["interval"], now),
            )
    pg.commit()
    print(f"已 seed schedules：{cfg}")


def main() -> None:
    ap = argparse.ArgumentParser(description="SQLite → Postgres 数据迁移")
    ap.add_argument("--sqlite", default="../data/posts.db", help="源 SQLite 路径")
    ap.add_argument("--truncate", action="store_true", help="先清空目标表（幂等重跑）")
    ap.add_argument("--source-env", default="../.env", help="读 XUEQIU_USERS 的源 .env")
    ap.add_argument("--data-dir", default="../data", help="找 schedule.json 的目录")
    args = ap.parse_args()

    if not os.path.exists(args.sqlite):
        sys.exit(f"❌ 找不到 SQLite：{args.sqlite}")

    sqlite_conn = sqlite3.connect(args.sqlite)
    pg = psycopg.connect(pg_conninfo())
    t0 = time.time()
    try:
        ensure_empty_or_truncate(pg, args.truncate)
        drop_stock_daily_indexes(pg)

        for table in TABLE_ORDER:
            n = copy_table(sqlite_conn, pg, table)
            print(f"✅ {table}: {n} 行", flush=True)

        rebuild_stock_daily_indexes(pg)
        fix_sequences(pg)
        seed_xueqiu_users(pg, read_xueqiu_users(args.source_env))
        seed_schedule(pg, args.data_dir)
    finally:
        sqlite_conn.close()
        pg.close()

    print(f"🎉 迁移完成，用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
