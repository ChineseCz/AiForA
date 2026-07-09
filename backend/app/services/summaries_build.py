"""各级总结构建（LLM 队列 worker 用）：从旧 main.py 移植分层归并逻辑。日→周/月→年，带缓存。"""
from datetime import date, timedelta

from app.repositories import sync_data as db
from app.services import summarizer

PERIOD_TYPES = ("daily", "weekly", "monthly", "yearly")


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


def ensure_daily(user_id: str, user_name: str, d: date, regen: bool = False) -> str | None:
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


def period_anchors(ptype: str, start: date, end: date) -> list[date]:
    """把 [start, end] 拆成该维度下需要生成的各周期锚点日期（从 web.py _period_anchors 移植）。"""
    anchors: list[date] = []
    if ptype == "daily":
        d = start
        while d <= end:
            anchors.append(d)
            d += timedelta(days=1)
    elif ptype == "weekly":
        d = start - timedelta(days=start.weekday())
        while d <= end:
            anchors.append(d)
            d += timedelta(days=7)
    elif ptype == "monthly":
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            anchors.append(date(y, m, 1))
            m += 1
            if m > 12:
                m = 1
                y += 1
    elif ptype == "yearly":
        for y in range(start.year, end.year + 1):
            anchors.append(date(y, 1, 1))
    return anchors


def gen_highlights_range(user_id: str, user_name: str, start: date, end: date) -> None:
    posts = db.get_top_posts(user_id, start.isoformat(), end.isoformat(), 12)
    if not posts:
        print(f"  （{user_name} 区间无帖子，跳过）")
        return
    label = f"{start.isoformat()} ~ {end.isoformat()}"
    content = summarizer.summarize_highlights(user_name, label, posts)
    key = f"{start.isoformat()}_{end.isoformat()}"
    db.save_summary(user_id, "highlights", key, content)
    print(f"  ✅ 精华 {key}")
