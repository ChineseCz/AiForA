"""大V提及 / 板块 / 名称匹配：从旧 stock.py 移植。数据走 repositories.sync_data。"""
import re
from datetime import date, timedelta

from app.repositories import sync_data as db
from app.services.external import sina

# 雪球标记格式，如 $贵州茅台(SH600519)$
TICKER_RE = re.compile(r"\$[^$()]+\((?:SZ|SH|BJ)?(\d{6})\)\$")

_STOCK_TABLE_HEADING = "提到的标的"


def pinyin_abbr(text: str) -> str:
    """中文转拼音首字母缩写，如 "贵州茅台" -> "GZMT"。"""
    from pypinyin import Style, lazy_pinyin

    return "".join(lazy_pinyin(text or "", style=Style.FIRST_LETTER)).upper()


def match_name_query(candidates: list[dict], query: str) -> list[dict]:
    q = (query or "").strip()
    if not q:
        return candidates
    q_upper = q.upper()
    out = []
    for row in candidates:
        name, code = row.get("name") or "", row.get("code") or ""
        if q in name or q in code or q_upper in pinyin_abbr(name):
            out.append(row)
    return out


def _recent_combined_text(days: int, user_ids: list[str]) -> str:
    ids = user_ids or [uid for uid, _ in db.get_distinct_users()]
    texts = db.get_recent_texts(ids, days)
    return "\n".join(t for _, t in texts)


def match_mentions(candidates: list[dict], days: int, user_ids: list[str]) -> list[dict]:
    if not candidates:
        return []
    combined_text = _recent_combined_text(days, user_ids)
    if not combined_text:
        return []
    coded_mentions = set(TICKER_RE.findall(combined_text))
    out = []
    for row in candidates:
        code = row.get("code") or ""
        name = row.get("name") or ""
        if code in coded_mentions or (name and name in combined_text):
            out.append(row)
    return out


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_bullish_names(md: str) -> set[str]:
    """从 AI 总结里的"提到的标的"表格挑出方向=看多的标的名称。

    按表头文字定位"名称"/"方向"列，不认列序号——旧总结是4列(名称/代码/方向/理由)，
    新总结是3列(名称/方向/理由)，位置不一样，AI偶尔还会在方向文字里夹带别的字。
    """
    if not md or _STOCK_TABLE_HEADING not in md:
        return set()
    lines = md.splitlines()
    names: set[str] = set()
    i, n = 0, len(lines)
    while i < n:
        if _STOCK_TABLE_HEADING not in lines[i]:
            i += 1
            continue
        i += 1
        while i < n and not lines[i].strip().startswith("|"):
            if lines[i].strip().startswith("#"):
                break
            i += 1
        if i >= n or not lines[i].strip().startswith("|"):
            continue
        header = _split_row(lines[i])
        i += 1
        if i < n and set(lines[i].strip()) <= set("-:| "):
            i += 1
        name_idx = header.index("名称") if "名称" in header else -1
        dir_idx = next((k for k, c in enumerate(header) if "方向" in c), -1)
        while i < n and lines[i].strip().startswith("|"):
            cells = _split_row(lines[i])
            if name_idx >= 0 and dir_idx >= 0 and len(cells) > max(name_idx, dir_idx):
                if "看多" in cells[dir_idx]:
                    nm = cells[name_idx].strip()
                    if nm and nm not in ("无", "-"):
                        names.add(nm)
            i += 1
    return names


def filter_bullish(candidates: list[dict], days: int, user_ids: list[str]) -> list[dict]:
    """在已经命中"提及"的候选里，只保留 AI 总结判定为"看多"的标的（按名称匹配"提到的标的"表格）。"""
    if not candidates:
        return []
    ids = user_ids or [uid for uid, _ in db.get_distinct_users()]
    summaries = db.get_recent_daily_summaries(ids, days)
    bullish_names: set[str] = set()
    for md in summaries:
        bullish_names |= parse_bullish_names(md)
    if not bullish_names:
        return []
    return [row for row in candidates if (row.get("name") or "") in bullish_names]


def get_stock_mentions(code: str, name: str, days: int = 90, limit: int = 20) -> list[dict]:
    since = (date.today() - timedelta(days=days)).isoformat()
    terms = [t for t in (code, name) if t]
    if not terms:
        return []
    candidates = db.search_posts_containing(terms, since, limit=200)
    out = []
    for p in candidates:
        combined = (p.get("text") or "") + (p.get("title") or "")
        if (code and code in TICKER_RE.findall(combined)) or (name and name in combined):
            out.append(p)
    return out[:limit]


def derive_bullish_sectors(days: int, user_ids: list[str]) -> list[str]:
    """哪些板块/概念名下，有至少一只股票被大V最近 days 天的AI总结判定为"看多"——
    与 filter_bullish/"大V看好"列同一套严谨判据（读结构化总结表的方向列，不是原文关键词命中），
    不是"板块名字被提到过"就算数。返回板块/概念名列表（不区分行业/概念，供"只看板块"筛选用）。
    """
    ids = user_ids or [uid for uid, _ in db.get_distinct_users()]
    summaries = db.get_recent_daily_summaries(ids, days)
    bullish_names: set[str] = set()
    for md in summaries:
        bullish_names |= parse_bullish_names(md)
    if not bullish_names:
        return []
    code_by_name = {r["name"]: r["code"] for r in db.get_latest_rows() if r.get("name")}
    codes = [code_by_name[n] for n in bullish_names if n in code_by_name]
    if not codes:
        return []
    by_code = db.get_sectors_by_codes(codes)
    names: set[str] = set()
    for secs in by_code.values():
        names.update(s["sector"] for s in secs)
    return sorted(names)


def get_sector_members(sector: str) -> list[str]:
    """先查缓存，没有/过期则实时拉取并回写缓存（懒加载，与旧实现一致）。

    雪球来源的板块（board_code 带 xq_ 前缀）没有可容器化的成分股接口——需要真实浏览器登录态，
    只能由宿主 browser 队列的 sync_xueqiu_sectors 任务批量预抓；这里读不到缓存就直接返回空，
    不去现拉（现算路径只对新浪来源有效）。
    """
    codes = db.get_sector_members_cached(sector)
    if codes is not None:
        return codes
    board_code = db.get_board_code(sector)
    if not board_code or board_code.startswith("xq_"):
        return []
    codes = sina.fetch_board_members(board_code)
    db.save_sector_members(sector, board_code, codes)
    return codes


def match_sector(candidates: list[dict], sector_names: list[str]) -> list[dict]:
    if not candidates or not sector_names:
        return []
    codes: set[str] = set()
    for name in sector_names:
        codes.update(get_sector_members(name))
    return [row for row in candidates if (row.get("code") or "") in codes]


_BULLISH_DAYS_DEFAULT = 7


def attach_sectors(rows: list[dict], bullish_days: int = _BULLISH_DAYS_DEFAULT) -> None:
    """给选股结果每行原地加 sectors（所属行业）+ concepts（概念题材）两个字段，按
    sector_catalog.kind 拆开，供前端表格分两列展示；再各配一个 bullish_* 子集字段，标出
    该行里哪些板块/概念名本身最近被大V看好（复用 derive_bullish_sectors 的判定——与
    "只看板块"筛选里"大V看多的板块"模式同一套口径），前端据此给对应标签描红框。
    这与"大V看好"列（针对股票本身）是两套独立判据，板块/概念看好 ≠ 该股票被看好。
    批量查一次，不逐行查。
    """
    if not rows:
        return
    codes = [r.get("code") for r in rows if r.get("code")]
    by_code = db.get_sectors_by_codes(codes)
    bullish_names = set(derive_bullish_sectors(bullish_days, []))
    for row in rows:
        secs = by_code.get(row.get("code") or "") or []
        row["sectors"] = [s["sector"] for s in secs if s["kind"] == "industry"]
        row["concepts"] = [s["sector"] for s in secs if s["kind"] == "concept"]
        row["bullish_sectors"] = [s for s in row["sectors"] if s in bullish_names]
        row["bullish_concepts"] = [s for s in row["concepts"] if s in bullish_names]


def get_bullish_users_map(days: int = _BULLISH_DAYS_DEFAULT) -> dict[str, list[str]]:
    """标的名称 -> 最近 days 天日总结里判定"看多"这只标的的大V昵称列表（去重、排序）。

    一次查完全部大V最近的日总结，反向建一张"名称→大V"的索引，供 attach_bullish_users
    对每行结果做 O(1) 查表，不逐行重跑总结解析。
    """
    users = db.get_distinct_users()
    name_by_id = dict(users)
    pairs = db.get_recent_daily_summaries_by_user([uid for uid, _ in users], days)
    out: dict[str, set[str]] = {}
    for uid, md in pairs:
        uname = name_by_id.get(uid, uid)
        for nm in parse_bullish_names(md):
            out.setdefault(nm, set()).add(uname)
    return {k: sorted(v) for k, v in out.items()}


def attach_bullish_users(rows: list[dict], days: int = _BULLISH_DAYS_DEFAULT) -> None:
    """给选股结果每行原地加一个 bullish_users 字段（哪些大V最近看多这只标的），按标的"名称"匹配
    （与 filter_bullish 用的是同一套按名称匹配逻辑，AI总结里没有稳定的代码列可用）。
    """
    if not rows:
        return
    bullish_map = get_bullish_users_map(days)
    for row in rows:
        row["bullish_users"] = bullish_map.get(row.get("name") or "", [])
