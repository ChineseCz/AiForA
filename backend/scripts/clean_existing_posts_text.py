"""一次性迁移：把 posts 表里已经落库的历史帖子正文，跑一遍 xueqiu.normalize_post_text 规则清洗。

只在加上这条清洗规则那一次跑一遍，把过去专栏类帖子里"编号/冒号被空行隔断"的旧数据修正过来；
以后新抓取的帖子在 xueqiu.py::clean_text 里已经自动清洗，不需要重复跑这个脚本。

只更新清洗后确实发生变化的行，不做全表无条件覆写。

用法（在 backend/ 目录，用装好 requirements.txt 的环境）：
    python -m scripts.clean_existing_posts_text
    python -m scripts.clean_existing_posts_text --dry-run   # 只打印会改动多少条，不写库
"""
import argparse
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sqlalchemy import text  # noqa: E402

from app.core.sync_db import sync_session  # noqa: E402
from app.scrapers.xueqiu import normalize_post_text  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计不写库")
    args = ap.parse_args()

    with sync_session() as s:
        rows = s.execute(text("SELECT id, text FROM posts WHERE text IS NOT NULL AND text != ''")).mappings().all()
        print(f"共 {len(rows)} 条帖子，开始清洗…")

        changed = 0
        for r in rows:
            old = r["text"]
            new = normalize_post_text(old)
            if new == old:
                continue
            changed += 1
            if not args.dry_run:
                s.execute(text("UPDATE posts SET text = :t WHERE id = :id"), {"t": new, "id": r["id"]})

        print(f"✅ {'（dry-run）' if args.dry_run else ''}共 {changed} 条发生变化" + ("，未写库" if args.dry_run else "，已写库"))


if __name__ == "__main__":
    main()
