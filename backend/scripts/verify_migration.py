"""迁移校验：逐表 COUNT 对齐 + 聚合抽查。任何不一致非零退出。"""
import argparse
import sqlite3
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import psycopg

from scripts.migrate_sqlite_to_pg import TABLE_ORDER, pg_conninfo

# 聚合抽查：(表, 描述, SQL)。SQL 在两侧都能跑（注意 PG 里 end/open 等需引号，这里用的列无冲突）。
AGG_CHECKS = [
    ("posts", "MAX(created_at)", "SELECT MAX(created_at) FROM posts"),
    ("posts", "SUM(like_count)", "SELECT COALESCE(SUM(like_count),0) FROM posts"),
    ("stock_daily", "MAX(trade_date)", "SELECT MAX(trade_date) FROM stock_daily"),
    ("stock_daily", "COUNT(DISTINCT code)", "SELECT COUNT(DISTINCT code) FROM stock_daily"),
    ("stock_finance", "COUNT(*) eps not null", "SELECT COUNT(*) FROM stock_finance WHERE eps IS NOT NULL"),
    ("stock_sector", "COUNT(DISTINCT sector)", "SELECT COUNT(DISTINCT sector) FROM stock_sector"),
]


def scalar(cur, sql: str):
    cur.execute(sql)
    return cur.fetchone()[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sqlite", default="../data/posts.db")
    args = ap.parse_args()

    slite = sqlite3.connect(args.sqlite)
    pg = psycopg.connect(pg_conninfo())
    scur = slite.cursor()
    pcur = pg.cursor()

    ok = True
    print(f"{'表':<22}{'SQLite':>14}{'Postgres':>14}   结果")
    print("-" * 66)
    for t in TABLE_ORDER:
        s = scalar(scur, f"SELECT COUNT(*) FROM {t}")
        p = scalar(pcur, f"SELECT COUNT(*) FROM {t}")
        match = s == p
        ok = ok and match
        print(f"{t:<22}{s:>14}{p:>14}   {'✅' if match else '❌ 不一致'}")

    print("\n聚合抽查：")
    for table, desc, sql in AGG_CHECKS:
        s = scalar(scur, sql)
        p = scalar(pcur, sql)
        match = str(s) == str(p)
        ok = ok and match
        print(f"  {table}.{desc:<24} sqlite={s!r} pg={p!r}  {'✅' if match else '❌'}")

    slite.close()
    pg.close()

    if not ok:
        print("\n❌ 校验失败：存在不一致。")
        sys.exit(1)
    print("\n🎉 校验通过：全部计数与抽查一致。")


if __name__ == "__main__":
    main()
