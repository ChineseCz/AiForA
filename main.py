"""命令行入口：抓取 + 日/周/月/年总结 + 精华提取。

用法示例：
  python main.py crawl                          # 抓取 .env 里配置的所有大V
  python main.py summary daily                  # 给所有人做"今天"的日总结
  python main.py summary daily --date 2026-06-29
  python main.py summary weekly                 # 本周总结（自动先补齐日总结）
  python main.py summary monthly --date 2026-06-15
  python main.py summary yearly  --date 2026-01-01
  python main.py highlights --period month      # 近一个月精华帖
  python main.py stats                          # 看库里有哪些人、多少帖子

总结按层级归并：日 -> 周/月 -> 年，避免一次喂太多内容。
"""
import argparse
import os
import re
import sys
from datetime import date, datetime, timedelta

# Windows 控制台默认 GBK，打印 emoji/部分字符会崩，这里统一切到 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
import db
import scraper
import summarizer

PERIODS = ("daily", "weekly", "monthly", "yearly")


# ---------- 通用工具 ----------
def parse_date(s: str | None) -> date:
    if not s:
        return date.today()
    return datetime.strptime(s, "%Y-%m-%d").date()


def sanitize(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name)[:40] or "user"


def write_report(period: str, key: str, user_name: str, content: str) -> str:
    folder = os.path.join(config.REPORTS_DIR, period)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{key}_{sanitize(user_name)}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(summarizer.DISCLAIMER + "\n" + content + "\n")
    return path


def week_dates(d: date) -> list[date]:
    monday = d - timedelta(days=d.weekday())
    return [monday + timedelta(days=i) for i in range(7)]


def week_key(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def month_dates(year: int, month: int) -> list[date]:
    d = date(year, month, 1)
    out = []
    while d.month == month and d.year == year:
        out.append(d)
        d += timedelta(days=1)
    return out


def resolve_targets(user_filter: str | None) -> list[tuple[str, str]]:
    users = db.get_distinct_users()
    if not users:
        print("⚠️  库里还没有帖子，请先运行：python main.py crawl")
        return []
    if user_filter:
        users = [
            (uid, name)
            for uid, name in users
            if user_filter == uid or user_filter in (name or "")
        ]
        if not users:
            print(f"⚠️  没找到匹配 '{user_filter}' 的用户。")
    return users


# ---------- 各级总结（带缓存）----------
def ensure_daily(user_id: str, user_name: str, d: date, regen: bool = False) -> str | None:
    """返回某天的日总结；无帖子返回 None。结果缓存进 DB。"""
    key = d.isoformat()
    if not regen:
        cached = db.get_summary(user_id, "daily", key)
        if cached:
            return cached
    posts = db.get_posts_on_date(user_id, key)
    if not posts:
        return None
    content = summarizer.summarize_daily(user_name, key, posts)
    db.save_summary(user_id, "daily", key, content)
    return content


def build_weekly(user_id: str, user_name: str, d: date, regen: bool = False) -> str | None:
    key = week_key(d)
    parts = []
    for day in week_dates(d):
        if day > date.today():
            break
        c = ensure_daily(user_id, user_name, day, regen)
        if c:
            parts.append((day.isoformat(), c))
    if not parts:
        return None
    content = summarizer.reduce_period(user_name, "周总结", key, parts, "日")
    db.save_summary(user_id, "weekly", key, content)
    return content


def build_monthly(user_id: str, user_name: str, d: date, regen: bool = False) -> str | None:
    key = f"{d.year}-{d.month:02d}"
    parts = []
    for day in month_dates(d.year, d.month):
        if day > date.today():
            break
        c = ensure_daily(user_id, user_name, day, regen)
        if c:
            parts.append((day.isoformat(), c))
    if not parts:
        return None
    content = summarizer.reduce_period(user_name, "月总结", key, parts, "日")
    db.save_summary(user_id, "monthly", key, content)
    return content


def build_yearly(user_id: str, user_name: str, d: date, regen: bool = False) -> str | None:
    key = str(d.year)
    parts = []
    for month in range(1, 13):
        first = date(d.year, month, 1)
        if first > date.today():
            break
        c = build_monthly(user_id, user_name, first, regen)
        if c:
            parts.append((f"{d.year}-{month:02d}", c))
    if not parts:
        return None
    content = summarizer.reduce_period(user_name, "年度归纳", key, parts, "月")
    db.save_summary(user_id, "yearly", key, content)
    return content


BUILDERS = {
    "daily": (ensure_daily, lambda d: d.isoformat()),
    "weekly": (build_weekly, week_key),
    "monthly": (build_monthly, lambda d: f"{d.year}-{d.month:02d}"),
    "yearly": (build_yearly, lambda d: str(d.year)),
}


# ---------- 子命令 ----------
def cmd_crawl(args):
    db.init_db()
    since = parse_date(args.since) if args.since else None
    until = parse_date(args.until) if args.until else None
    scraper.crawl_all(since, until)


def cmd_login(args):
    db.init_db()
    scraper.login()


def cmd_serve(args):
    import web
    web.run(host=args.host, port=args.port)


def cmd_summary(args):
    db.init_db()
    d = parse_date(args.date)
    builder, keyfn = BUILDERS[args.period]
    for uid, uname in resolve_targets(args.user):
        print(f"… 正在为 {uname}（{uid}）生成 {args.period} 总结 …")
        content = builder(uid, uname, d, args.regen)
        if not content:
            print(f"   {uname}：该周期内没有帖子，跳过。")
            continue
        path = write_report(args.period, keyfn(d), uname, content)
        print(f"   ✅ {path}")


def cmd_highlights(args):
    db.init_db()
    today = date.today()
    spans = {"week": 7, "month": 30, "year": 365}
    days = spans.get(args.period, 30)
    start = (today - timedelta(days=days)).isoformat()
    end = today.isoformat()
    label = f"近{days}天"
    for uid, uname in resolve_targets(args.user):
        posts = db.get_top_posts(uid, start, end, args.topn)
        if not posts:
            print(f"   {uname}：区间内无帖子，跳过。")
            continue
        print(f"… 正在为 {uname} 提炼精华帖 …")
        content = summarizer.summarize_highlights(uname, label, posts)
        key = f"{end}_{args.period}"
        db.save_summary(uid, "highlights", key, content)
        path = write_report("highlights", key, uname, content)
        print(f"   ✅ {path}")


def cmd_stock_sync(args):
    db.init_db()
    import stock
    stock.sync_daily_snapshot()


def cmd_stock_backfill(args):
    db.init_db()
    import stock
    stock.backfill_history(args.days, args.delay)


def cmd_stock_sync_finance(args):
    db.init_db()
    import stock
    stock.sync_finance_snapshot()


def cmd_stock_sync_sector_members(args):
    db.init_db()
    import stock
    stock.sync_all_sector_members()


def cmd_stats(args):
    db.init_db()
    s = db.get_stats()
    print(f"帖子总数：{s['total']}")
    for u in s["per_user"]:
        print(f"  - {u['user_name']}：{u['c']} 条（{u['first']} ~ {u['last']}）")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="雪球大V帖子抓取 + AI 总结")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="打开浏览器登录雪球（首次使用先跑这个）").set_defaults(func=cmd_login)

    cp = sub.add_parser("crawl", help="抓取 .env 中配置的大V的新帖")
    cp.add_argument("--since", help="只抓该日期及之后 YYYY-MM-DD")
    cp.add_argument("--until", help="只抓该日期及之前 YYYY-MM-DD")
    cp.set_defaults(func=cmd_crawl)

    sp = sub.add_parser("summary", help="生成 日/周/月/年 总结")
    sp.add_argument("period", choices=PERIODS)
    sp.add_argument("--date", help="目标日期 YYYY-MM-DD，默认今天")
    sp.add_argument("--user", help="只处理某个用户（id 或昵称片段），默认全部")
    sp.add_argument("--regen", action="store_true", help="忽略缓存，重新生成")
    sp.set_defaults(func=cmd_summary)

    hp = sub.add_parser("highlights", help="提炼精华帖")
    hp.add_argument("--period", choices=("week", "month", "year"), default="month")
    hp.add_argument("--user", help="只处理某个用户")
    hp.add_argument("--topn", type=int, default=10, help="取互动量前 N 条")
    hp.set_defaults(func=cmd_highlights)

    sub.add_parser("stats", help="查看库内统计").set_defaults(func=cmd_stats)

    sub.add_parser("stock-sync", help="同步一次全市场A股行情快照（建议收盘后运行）").set_defaults(func=cmd_stock_sync)

    bp = sub.add_parser("stock-backfill", help="批量回补历史K线（首次用预设策略前跑一次；会打开一个真实浏览器窗口，约1小时跑完）")
    bp.add_argument("--days", type=int, default=60, help="回补最近多少个交易日，默认60")
    bp.add_argument("--delay", type=float, default=0.5, help="每只股票请求间隔秒数（随机抖动），默认0.5秒")
    bp.set_defaults(func=cmd_stock_backfill)

    sub.add_parser("stock-sync-finance", help="同步一次全市场最新财报指标（EPS/ROE/净利润同比/营收同比/毛利率）").set_defaults(
        func=cmd_stock_sync_finance
    )

    sub.add_parser(
        "stock-sync-sector-members",
        help="全量同步所有板块（行业+概念）的成分股，供个股详情页「所属板块」反查完整覆盖（需先运行过板块名单同步）",
    ).set_defaults(func=cmd_stock_sync_sector_members)

    wp = sub.add_parser("serve", help="启动本地网页看板")
    wp.add_argument("--host", default="127.0.0.1", help="监听地址，默认仅本机")
    wp.add_argument("--port", type=int, default=5000, help="端口，默认 5000")
    wp.set_defaults(func=cmd_serve)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
