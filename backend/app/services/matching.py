"""大V提及 / 板块 / 名称匹配：从旧 stock.py 移植。数据走 repositories.sync_data。"""
import re
from datetime import date, timedelta

from app.repositories import sync_data as db
from app.services.external import sina

# 雪球标记格式，如 $贵州茅台(SH600519)$
TICKER_RE = re.compile(r"\$[^$()]+\((?:SZ|SH|BJ)?(\d{6})\)\$")


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


def _recent_combined_text(days: int, user_id: str) -> str:
    user_ids = [user_id] if user_id else [uid for uid, _ in db.get_distinct_users()]
    texts = db.get_recent_texts(user_ids, days)
    return "\n".join(t for _, t in texts)


def match_mentions(candidates: list[dict], days: int, user_id: str) -> list[dict]:
    if not candidates:
        return []
    combined_text = _recent_combined_text(days, user_id)
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


def extract_sectors_from_text(text: str, catalog_names: list[str]) -> set[str]:
    if not text:
        return set()
    return {name for name in catalog_names if name and name in text}


def derive_bullish_sectors(days: int, user_id: str) -> list[str]:
    combined_text = _recent_combined_text(days, user_id)
    if not combined_text:
        return []
    catalog_names = [c["name"] for c in db.get_sector_catalog()]
    return sorted(extract_sectors_from_text(combined_text, catalog_names))


def get_sector_members(sector: str) -> list[str]:
    """先查缓存，没有/过期则实时拉取并回写缓存（懒加载，与旧实现一致）。"""
    codes = db.get_sector_members_cached(sector)
    if codes is not None:
        return codes
    board_code = db.get_board_code(sector)
    if not board_code:
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
