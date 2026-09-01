"""Evaluate stock mentions in public-account articles against later market data."""
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import opinions


WINDOWS = (1, 3, 5, 10, 20)
CODE_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
POSITIVE = ("看多", "上涨", "启动", "突破", "机会", "买入", "加仓", "利好", "龙头")
NEGATIVE = ("看空", "下跌", "回落", "风险", "卖出", "减仓", "利空", "见顶")


def _direction(text_value: str) -> str:
    # 免责声明通常包含大量“风险/谨慎”等词，不应改变文章实际方向。
    text_value = re.split(r"风险提示|股市有风险|不构成投资买卖建议", text_value, maxsplit=1)[0]
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


async def _instrument_aliases(session: AsyncSession) -> dict[str, list[dict[str, str]]]:
    rows = (await session.execute(text("""
        SELECT code, MAX(name) AS name
        FROM stock_daily
        WHERE name IS NOT NULL AND name <> ''
        GROUP BY code
    """))).mappings().all()
    instruments = [{"code": str(row["code"]), "name": str(row["name"])} for row in rows]
    aliases: dict[str, list[dict[str, str]]] = {}
    for item in instruments:
        name = item["name"].replace("XD", "").replace("XR", "").replace("*ST", "")
        candidates = {name}
        # 对正文常见的简称，只有在全市场唯一时才加入，避免“青岛”等泛称误匹配。
        for length in (2, 3, 4):
            if len(name) >= length:
                candidates.add(name[:length])
        for alias in candidates:
            if len(alias) >= 2:
                aliases.setdefault(alias, []).append(item)
    return {alias: items for alias, items in aliases.items() if len({x["code"] for x in items}) == 1}


async def review_posts(
    session: AsyncSession, user_id: str = "", start: str = "", end: str = "", limit: int = 100,
    group_by_day: bool = False,
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

    alias_map = await _instrument_aliases(session)
    by_code = {item["code"]: item for items in alias_map.values() for item in items}
    claims_by_post = opinions.get_claims([str(row["id"]) for row in rows])
    results = []
    for post in rows:
        content = f"{post['title'] or ''}\n{post['text'] or ''}"
        stored_claims = claims_by_post.get(str(post["id"]), [])
        ready_claims = [claim for claim in stored_claims if claim.get("status") == "ready" and not claim.get("ignored")]
        names = {}
        if ready_claims:
            for claim in ready_claims:
                code = str(claim.get("code") or "")
                if code in by_code:
                    names[code] = {**by_code[code], "claim": claim}
                    continue
                claim_name = str(claim.get("name") or "").strip()
                for item in alias_map.get(claim_name, []):
                    names[item["code"]] = {**item, "claim": claim}
            directions = [claim.get("direction") for claim in ready_claims]
            direction = max(set(directions), key=directions.count) if directions else _direction(content)
        else:
            codes = [code for code in dict.fromkeys(CODE_RE.findall(content)) if code in by_code]
            names = {code: by_code[code] for code in codes}
            for alias, alias_items in alias_map.items():
                if alias in content:
                    names.update({item["code"]: item for item in alias_items})
            direction = _direction(content)
        items = []
        for target in names.values():
            quotes = (await session.execute(text("""
                SELECT trade_date, close FROM stock_daily
                WHERE code = :code AND trade_date > :post_date
                ORDER BY trade_date LIMIT 21
            """), {"code": target["code"], "post_date": post["date"]})).mappings().all()
            if not quotes:
                items.append({"code": target["code"], "name": target["name"], "performance": {}, "excess": {},
                              "available_windows": [], "quote_count": 0, "data_status": "no_future_quotes"})
                continue
            baseline = (await session.execute(text("""
                SELECT trade_date, close FROM index_daily
                WHERE code = 'sh000300' AND trade_date > :post_date
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
            item = {
                "code": target["code"], "name": target["name"],
                "performance": performance, "excess": excess,
                "available_windows": [str(window) for window in WINDOWS if performance[str(window)] is not None],
                "quote_count": len(quotes),
            }
            if target.get("claim"):
                item["claim"] = target["claim"]
            items.append(item)
        available_windows = sorted({
            window for target in items for window in target.get("available_windows", [])
        }, key=int)
        if not names:
            verdict = "待验证"
        elif not any(target.get("quote_count", 0) for target in items):
            verdict = "暂无行情"
        elif len(available_windows) < len(WINDOWS):
            verdict = "部分可验证"
        else:
            verdict = "可验证"
        results.append({
            "id": post["id"], "user_id": post["user_id"], "user_name": post["user_name"],
            "date": post["date"], "title": post["title"], "url": post["url"],
            "text": post["text"],
            "direction": direction, "targets": items,
            "claims": stored_claims,
            "extraction_status": stored_claims[0]["status"] if stored_claims else "missing",
            "verdict": verdict,
            "available_windows": available_windows,
        })
    article_total = len(results)
    if group_by_day:
        results = _merge_daily_results(results)
    summary = _summary(results)
    summary["article_total"] = article_total
    return {"total": len(results), "article_total": article_total, "items": results, "windows": WINDOWS, "summary": summary}


def _merge_daily_results(results: list[dict]) -> list[dict]:
    """Merge same-user same-day posts while retaining every target and claim."""
    grouped: dict[tuple[str, str], dict] = {}
    for item in results:
        key = (str(item.get("user_id") or ""), str(item.get("date") or ""))
        current = grouped.get(key)
        if current is None:
            current = {**item, "id": f"daily:{key[0]}:{key[1]}", "article_count": 0,
                       "titles": [], "claims": [], "targets": []}
            grouped[key] = current
        current["article_count"] += 1
        title = item.get("title") or (str(item.get("text") or "").splitlines() or [""])[0]
        if title and title not in current["titles"]:
            current["titles"].append(title)
        current["claims"].extend(item.get("claims") or [])
        for target in item.get("targets") or []:
            if not any(existing.get("code") == target.get("code") for existing in current["targets"]):
                current["targets"].append(target)
        directions = [part.get("direction") for part in current["claims"] if part.get("direction")]
        current["direction"] = max(set(directions), key=directions.count) if directions else current.get("direction")
    merged = []
    for item in grouped.values():
        item["title"] = "；".join(item.pop("titles")) or "当日观点"
        item["text"] = ""
        available = sorted({window for target in item["targets"] for window in target.get("available_windows", [])}, key=int)
        item["available_windows"] = available
        has_quotes = any(target.get("quote_count", 0) for target in item["targets"])
        item["verdict"] = "待验证" if not item["targets"] else ("暂无行情" if not has_quotes else ("部分可验证" if len(available) < len(WINDOWS) else "可验证"))
        merged.append(item)
    return merged


def _summary(results: list[dict]) -> dict:
    """Aggregate only observations with actual prices; missing data is not a zero return."""
    observations = {str(window): [] for window in WINDOWS}
    excess_observations = {str(window): [] for window in WINDOWS}
    direction_counts: dict[str, int] = {}
    by_user: dict[str, dict] = {}
    verified = 0
    claim_count = 0
    target_count = 0
    for item in results:
        direction = item.get("direction") or "未定"
        direction_counts[direction] = direction_counts.get(direction, 0) + 1
        claim_count += sum(1 for claim in item.get("claims", []) if claim.get("status") == "ready" and not claim.get("ignored"))
        targets = item.get("targets") or []
        target_count += len(targets)
        if any(target.get("quote_count", 0) for target in targets):
            verified += 1
        user_key = str(item.get("user_id") or "")
        user_stat = by_user.setdefault(user_key, {"user_id": item.get("user_id"), "user_name": item.get("user_name"), "posts": 0, "verified": 0, "targets": 0})
        user_stat["posts"] += 1
        user_stat["verified"] += bool(targets)
        user_stat["targets"] += len(targets)
        for target in targets:
            for window in WINDOWS:
                key = str(window)
                value = target.get("performance", {}).get(key)
                excess = target.get("excess", {}).get(key)
                if value is not None:
                    observations[key].append(value)
                if excess is not None:
                    excess_observations[key].append(excess)
    windows = {}
    for window in WINDOWS:
        key = str(window)
        values = observations[key]
        excess_values = excess_observations[key]
        windows[key] = {
            "samples": len(values),
            "average_return": round(sum(values) / len(values), 2) if values else None,
            "average_excess": round(sum(excess_values) / len(excess_values), 2) if excess_values else None,
            "positive_rate": round(sum(value > 0 for value in values) / len(values) * 100, 2) if values else None,
        }
    return {
        "posts": len(results),
        "verified_posts": verified,
        "verification_rate": round(verified / len(results) * 100, 2) if results else None,
        "claims": claim_count,
        "targets": target_count,
        "direction_counts": direction_counts,
        "windows": windows,
        "by_user": list(by_user.values()),
    }
