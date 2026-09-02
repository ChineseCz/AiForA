"""Evaluate stock mentions in public-account articles against later market data."""
import hashlib
import json
import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories import opinions


WINDOWS = (1, 3, 5, 7, 10, 20, 60, 120)
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


def _claims_signature(claims: list[dict]) -> str:
    """Identify the extracted and mapped opinion state used by a snapshot."""
    relevant = [
        {
            "id": claim.get("id"), "code": claim.get("code"), "name": claim.get("name"),
            "direction": claim.get("direction"), "claim": claim.get("claim"),
            "evidence": claim.get("evidence"), "confidence": claim.get("confidence"),
            "status": claim.get("status"), "ignored": claim.get("ignored"),
        }
        for claim in claims
    ]
    encoded = json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
    group_by_day: bool = False, progress_callback=None, cancel_callback=None, target_threshold: float = 3.0,
    saved_only: bool = False,
) -> dict:
    conditions = ["date != ''"]
    params: dict = {}
    limit_value = max(0, int(limit or 0))
    if user_id:
        conditions.append("user_id = :user_id")
        params["user_id"] = user_id
    if start:
        conditions.append("date >= :start")
        params["start"] = start
    if end:
        conditions.append("date <= :end")
        params["end"] = end
    limit_clause = " LIMIT :limit" if limit_value else ""
    if limit_value:
        params["limit"] = limit_value
    rows = (await session.execute(text(f"""
        SELECT id, user_id, user_name, date, title, text, url
        FROM posts WHERE {' AND '.join(conditions)}
        ORDER BY created_at DESC{limit_clause}
    """), params)).mappings().all()

    summary_titles = await _daily_summary_titles(session, rows)

    alias_map = await _instrument_aliases(session)
    by_code = {item["code"]: item for items in alias_map.values() for item in items}
    claims_by_post = opinions.get_claims([str(row["id"]) for row in rows])
    snapshots_by_post = opinions.get_review_snapshots([str(row["id"]) for row in rows])
    results = []
    pending = []
    required_codes = set()
    reused_count = 0
    for post in rows:
        if cancel_callback and cancel_callback():
            raise RuntimeError("复盘任务已取消")
        post_id = str(post["id"])
        stored_claims = claims_by_post.get(post_id, [])
        snapshot = snapshots_by_post.get(post_id)
        if (
            snapshot and snapshot.get("finalized")
            and snapshot["payload"].get("version") == 1
            and snapshot["payload"].get("claims_signature") == _claims_signature(stored_claims)
            and isinstance(snapshot["payload"].get("result"), dict)
        ):
            results.append(snapshot["payload"]["result"])
            reused_count += 1
            continue
        if saved_only:
            continue
        content = f"{post['title'] or ''}\n{post['text'] or ''}"
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
        required_codes.update(names)
        pending.append((post, stored_claims, ready_claims, names, direction))

    total_posts = len(rows)
    if progress_callback:
        progress_callback({"total": total_posts, "processed": reused_count, "reused": reused_count, "computed": 0, "finalized": 0})

    # A review only needs bars after the earliest article date. Avoid loading
    # the complete history for every matched code into API memory.
    min_post_date = min((post["date"] for post, *_ in pending), default="")
    if required_codes and min_post_date:
        code_params = {f"c{i}": code for i, code in enumerate(sorted(required_codes))}
        code_placeholders = ", ".join(f":c{i}" for i in range(len(code_params)))
        code_params["min_post_date"] = min_post_date
        quote_rows = (await session.execute(text(f"""
            SELECT code, trade_date, close
            FROM stock_daily
            WHERE code IN ({code_placeholders}) AND trade_date > :min_post_date
            ORDER BY code, trade_date
        """), code_params)).mappings().all()
    else:
        quote_rows = []
    quotes_by_code = {}
    for row in quote_rows:
        quotes_by_code.setdefault(str(row["code"]), []).append(row)
    benchmark_rows = (await session.execute(text("""
        SELECT trade_date, close FROM index_daily
        WHERE code = 'sh000300' AND trade_date > :min_post_date
        ORDER BY trade_date
    """), {"min_post_date": min_post_date})).mappings().all()
    benchmark_by_date = {}
    benchmark_dates = [row["trade_date"] for row in benchmark_rows]
    for post, *_ in pending:
        start_index = next((index for index, date in enumerate(benchmark_dates) if date > post["date"]), len(benchmark_rows))
        future = benchmark_rows[start_index:start_index + 121]
        benchmark_by_date[post["date"]] = future

    pending_snapshots = []
    computed_count = 0
    finalized_count = 0
    for post, stored_claims, ready_claims, names, direction in pending:
        if cancel_callback and cancel_callback():
            raise RuntimeError("复盘任务已取消")
        items = []
        for target in names.values():
            quotes = [row for row in quotes_by_code.get(target["code"], []) if row["trade_date"] > post["date"]][:121]
            if not quotes:
                items.append({"code": target["code"], "name": target["name"], "performance": {}, "excess": {},
                              "available_windows": [], "quote_count": 0, "data_status": "no_future_quotes"})
                continue
            baseline = benchmark_by_date.get(post["date"], [])
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
                "direction": (target.get("claim") or {}).get("direction") or direction,
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
        result = {
            "id": post["id"], "user_id": post["user_id"], "user_name": post["user_name"],
            "date": post["date"], "title": summary_titles.get((str(post["user_id"] or ""), str(post["date"] or ""))) or post["title"], "url": post["url"],
            "text": post["text"],
            "source_title": post["title"],
            "summary_title": summary_titles.get((str(post["user_id"] or ""), str(post["date"] or ""))),
            "direction": direction, "targets": items,
            "claims": stored_claims,
            "extraction_status": stored_claims[0]["status"] if stored_claims else "missing",
            "verdict": verdict,
            "available_windows": available_windows,
        }
        results.append(result)
        finalized = bool(
            items and all(len(target.get("available_windows", [])) == len(WINDOWS) for target in items)
        )
        pending_snapshots.append((
            str(post["id"]),
            {"version": 1, "claims_signature": _claims_signature(stored_claims), "result": result},
            finalized,
        ))
        computed_count += 1
        finalized_count += int(finalized)
        if progress_callback and (computed_count % 25 == 0 or computed_count == len(pending)):
            progress_callback({
                "total": total_posts, "processed": reused_count + computed_count,
                "reused": reused_count, "computed": computed_count, "finalized": finalized_count,
            })
    opinions.save_review_snapshots(pending_snapshots)
    article_total = len(results)
    has_more = bool(limit_value and article_total >= limit_value)
    if group_by_day:
        results = _merge_daily_results(results)
    summary = _summary(results, target_threshold=target_threshold)
    summary["article_total"] = article_total
    return {"total": len(results), "article_total": article_total, "has_more": has_more, "items": results, "windows": WINDOWS, "summary": summary}


async def _daily_summary_titles(session: AsyncSession, rows) -> dict[tuple[str, str], str]:
    pairs = {(str(row["user_id"] or ""), str(row["date"] or "")) for row in rows if row["user_id"] and row["date"]}
    if not pairs:
        return {}
    clauses = []
    params = {}
    for index, (user_id, period_key) in enumerate(pairs):
        clauses.append(f"(user_id = :su{index} AND period_key = :sd{index})")
        params[f"su{index}"] = user_id
        params[f"sd{index}"] = period_key
    rows = (await session.execute(text(
        "SELECT user_id, period_key, content FROM summaries "
        "WHERE period_type = 'daily' AND (" + " OR ".join(clauses) + ")"
    ), params)).mappings().all()
    result = {}
    for row in rows:
        for line in str(row["content"] or "").splitlines():
            heading = line.strip()
            if heading.startswith("## "):
                result[(str(row["user_id"]), str(row["period_key"]))] = heading[3:].strip()
                break
    return result


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
        item["title"] = item.get("summary_title") or "；".join(item.pop("titles")) or "当日观点"
        item["text"] = ""
        available = sorted({window for target in item["targets"] for window in target.get("available_windows", [])}, key=int)
        item["available_windows"] = available
        has_quotes = any(target.get("quote_count", 0) for target in item["targets"])
        item["verdict"] = "待验证" if not item["targets"] else ("暂无行情" if not has_quotes else ("部分可验证" if len(available) < len(WINDOWS) else "可验证"))
        merged.append(item)
    return merged


def _summary(results: list[dict], target_threshold: float = 3.0) -> dict:
    """Aggregate only observations with actual prices; missing data is not a zero return."""
    observations = {str(window): [] for window in WINDOWS}
    excess_observations = {str(window): [] for window in WINDOWS}
    direction_counts: dict[str, int] = {}
    accuracy = {
        str(window): {"samples": 0, "correct": 0, "benchmark_wins": 0, "target_hits": 0,
                      "correct_rate": None, "benchmark_win_rate": None, "target_hit_rate": None,
                      "average_return": None, "average_excess": None, "returns": [], "excesses": []}
        for window in WINDOWS
    }
    by_user: dict[str, dict] = {}
    user_windows: dict[str, dict[str, dict]] = {}
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
        user_windows.setdefault(user_key, {str(window): {"samples": 0, "correct": 0, "returns": [], "excesses": []} for window in WINDOWS})
        for target in targets:
            target_direction = target.get("direction") or direction
            for window in WINDOWS:
                key = str(window)
                value = target.get("performance", {}).get(key)
                excess = target.get("excess", {}).get(key)
                if value is not None:
                    observations[key].append(value)
                if excess is not None:
                    excess_observations[key].append(excess)
                if value is not None and target_direction in ("看多", "看空"):
                    stat = accuracy[key]
                    stat["samples"] += 1
                    stat["correct"] += int(value > 0 if target_direction == "看多" else value < 0)
                    stat["benchmark_wins"] += int(excess is not None and excess > 0)
                    stat["target_hits"] += int(value > target_threshold if target_direction == "看多" else value < -target_threshold)
                    stat["returns"].append(value)
                    if excess is not None:
                        stat["excesses"].append(excess)
                    user_stat_window = user_windows[user_key][key]
                    user_stat_window["samples"] += 1
                    user_stat_window["correct"] += int(value > 0 if target_direction == "看多" else value < 0)
                    user_stat_window["returns"].append(value)
                    if excess is not None:
                        user_stat_window["excesses"].append(excess)
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
        stat = accuracy[key]
        accuracy[key] = {
            "samples": stat["samples"],
            "correct_rate": round(stat["correct"] / stat["samples"] * 100, 2) if stat["samples"] else None,
            "benchmark_win_rate": round(stat["benchmark_wins"] / stat["samples"] * 100, 2) if stat["samples"] else None,
            "target_hit_rate": round(stat["target_hits"] / stat["samples"] * 100, 2) if stat["samples"] else None,
            "average_return": round(sum(stat["returns"]) / len(stat["returns"]), 2) if stat["returns"] else None,
            "average_excess": round(sum(stat["excesses"]) / len(stat["excesses"]), 2) if stat["excesses"] else None,
        }
    rankings = []
    for user_key, user_stat in by_user.items():
        ranking = {**user_stat, "accuracy": {}}
        for window in WINDOWS:
            key = str(window)
            stat = user_windows[user_key][key]
            ranking["accuracy"][key] = {
                "samples": stat["samples"],
                "correct_rate": round(stat["correct"] / stat["samples"] * 100, 2) if stat["samples"] else None,
                "average_return": round(sum(stat["returns"]) / len(stat["returns"]), 2) if stat["returns"] else None,
                "average_excess": round(sum(stat["excesses"]) / len(stat["excesses"]), 2) if stat["excesses"] else None,
            }
        rankings.append(ranking)
    rankings.sort(key=lambda item: (item["accuracy"]["20"]["correct_rate"] is not None, item["accuracy"]["20"]["correct_rate"] or -1), reverse=True)
    monthly_data: dict[str, dict] = {}
    for item in results:
        month = str(item.get("date") or "")[:7]
        if len(month) != 7:
            continue
        month_stat = monthly_data.setdefault(
            month, {"month": month, "posts": 0, "targets": 0,
                    "windows": {str(w): {"returns": [], "correct": 0, "samples": 0} for w in WINDOWS}}
        )
        month_stat["posts"] += 1
        month_stat["targets"] += len(item.get("targets") or [])
        for target in item.get("targets") or []:
            target_direction = target.get("direction") or item.get("direction")
            for window in WINDOWS:
                value = target.get("performance", {}).get(str(window))
                if value is None:
                    continue
                stat = month_stat["windows"][str(window)]
                stat["returns"].append(value)
                if target_direction in ("看多", "看空"):
                    stat["samples"] += 1
                    stat["correct"] += int(value > 0 if target_direction == "看多" else value < 0)
    monthly = []
    for month in sorted(monthly_data):
        month_item = monthly_data[month]
        month_item["windows"] = {
            key: {
                "samples": stat["samples"],
                "average_return": round(sum(stat["returns"]) / len(stat["returns"]), 2) if stat["returns"] else None,
                "correct_rate": round(stat["correct"] / stat["samples"] * 100, 2) if stat["samples"] else None,
            }
            for key, stat in month_item["windows"].items()
        }
        monthly.append(month_item)
    return {
        "posts": len(results),
        "verified_posts": verified,
        "verification_rate": round(verified / len(results) * 100, 2) if results else None,
        "claims": claim_count,
        "targets": target_count,
        "direction_counts": direction_counts,
        "windows": windows,
        "accuracy": accuracy,
        "by_user": list(by_user.values()),
        "rankings": rankings,
        "monthly": monthly,
    }
