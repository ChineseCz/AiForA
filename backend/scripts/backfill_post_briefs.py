"""一次性回填：给库里已存在、正文超长且还没有一句话总结（brief IS NULL）的历史帖子批量生成。

只在加上"帖子流一句话总结"这个功能那一次跑一遍，把过去攒下的长帖子补上摘要；
以后新抓取的长帖子在采集流程里已经自动派发 LLM 任务生成，不需要重复跑这个脚本。

用法（在 backend/ 目录，用装好 requirements.txt 的环境，需要 RELAY_API_KEY）：
    python -m scripts.backfill_post_briefs
    python -m scripts.backfill_post_briefs --limit 50   # 只处理前 N 条，调试用
"""
import argparse
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.sync_db import sync_session  # noqa: E402
from app.repositories import sync_data as db  # noqa: E402
from app.services import summarizer  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少条，0=不限")
    ap.add_argument("--delay", type=float, default=0.5, help="每条之间的间隔秒数")
    args = ap.parse_args()

    with sync_session() as s:
        rows = s.execute(text(
            "SELECT id, title, text FROM posts "
            "WHERE brief IS NULL AND length(text) > :n ORDER BY created_at DESC"
        ), {"n": settings.post_brief_min_length}).mappings().all()

    if args.limit:
        rows = rows[:args.limit]
    total = len(rows)
    print(f"共 {total} 条长帖子待生成一句话总结…")

    done, failed = 0, 0
    for i, r in enumerate(rows, 1):
        try:
            brief = summarizer.summarize_post_brief(r["text"], r.get("title") or "")
        except Exception as e:  # noqa: BLE001
            print(f"  [{i}/{total}] {r['id']} 失败：{e}")
            failed += 1
            time.sleep(args.delay)
            continue
        if brief:
            db.save_post_brief(r["id"], brief)
            done += 1
        time.sleep(args.delay)

    print(f"✅ 完成：成功 {done} 条，失败 {failed} 条")


if __name__ == "__main__":
    main()
