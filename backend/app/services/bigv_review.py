"""Evaluate stock mentions in public-account articles against later market data."""
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


WINDOWS = (1, 3, 5, 10, 20)
CODE_RE = re.compile(r"(?<!\d)([036]\d{5}|[68]\d{5})(?!\d)")
POSITIVE = ("看多", "上涨", "启动", "突破", "机会", "买入", "加仓", "利好", "龙头")
NEGATIVE = ("看空", "下跌", "回落", "风险", "卖出", "减仓", "利空", "见顶")


def _direction(text_value: str) -> str:
    positive = sum(text_value.count(word) for word in POSITIVE)
    negative = sum(text_value.count(word) for word in NEGATIVE)
    if positive > negative:
        return "看多"
    if negative > positive:
        return "看空"
    return "未定向"


def _pct(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return round((end / start - 1) * 100, 2)


async def review_posts(
    session: AsyncSession, user_id: str = "", start: str = "", end: str = "", limit: int = 100
) -> dict:
    conditions = ["date != ''"]
    params: dict = {"limit": max(1, min(limit, 200))}
    if user_id:
        conditions.append("user_id = :user_id")
        params["user_id"] = user_id
    if start:
        conditions.append("date >= :start")
        params["start"] = start
    if end:
        conditions.append("date <= :end")
        params["end"] = end
    rows = (await session.execute(text(f"""
        SELECT id, user_id, user_name, date, title, text, url
        FROM posts WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC LIMIT :limit
    """), params)).mappings().all()

    results = []
    for post in rows:
        content = f"{post['title'] or ''}\n{post['text'] or ''}"
        codes = list(dict.fromkeys(CODE_RE.findall(content)))
        names = []
        for code in codes:
            row = (await session.execute(text(
                "SELECT DISTINCT name FROM stock_daily WHERE code = :code AND name IS NOT NULL LIMIT 1"
            ), {"code": code})).scalar()
            if row:
                names.append({"code": code, "name": row})

        direction = _direction(content)
        items = []
        for target in names:
            quotes = (await session.execute(text("""
                SELECT trade_date, close FROM stock_daily
                WHERE code = :code AND trade_date > :post_date
                ORDER BY trade_date LIMIT 21
            """), {"code": target["code"], "post_date": post["date"]})).mappings().all()
            if not quotes:
                continue
            baseline = (await session.execute(text("""
                SELECT trade_date, close FROM stock_daily
                WHERE code IN ('000300', 'sh000300') AND trade_date > :post_date
                ORDER BY trade_date LIMIT 21
            """), {"post_date": post["date"]})).mappings().all()
            first = quotes[0]["close"]
            benchmark_first = baseline[0]["close"] if baseline else None
            performance = {}
            excess = {}
            for window in WINDOWS:
                price = quotes[window]["close"] if len(quotes) > window else None
                bench_price = baseline[window]["close"] if len(baseline) > window else None
                performance[str(window)] = _pct(first, price)
                excess[str(window)] = (
                    round(performance[str(window)] - _pct(benchmark_first, bench_price), 2)
                    if performance[str(window)] is not None and _pct(benchmark_first, bench_price) is not None
                    else None
                )
            items.append({"code": target["code"], "name": target["name"], "performance": performance, "excess": excess})
        results.append({
            "id": post["id"], "user_id": post["user_id"], "user_name": post["user_name"],
            "date": post["date"], "title": post["title"], "url": post["url"],
            "direction": direction, "targets": items,
            "verdict": "可验证" if items else "无法验证",
        })
    return {"total": len(results), "items": results, "windows": WINDOWS}
