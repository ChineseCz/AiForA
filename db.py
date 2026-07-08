"""SQLite 存储层：帖子去重入库 + 总结缓存。"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import date, timedelta

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id            TEXT PRIMARY KEY,   -- 雪球 status id
    user_id       TEXT,
    user_name     TEXT,
    created_at    INTEGER,            -- 毫秒时间戳
    date          TEXT,               -- YYYY-MM-DD（本地时区）
    text          TEXT,               -- 清洗后的正文
    title         TEXT,
    url           TEXT,
    like_count    INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    reply_count   INTEGER DEFAULT 0,
    fav_count     INTEGER DEFAULT 0,
    raw_json      TEXT,
    images        TEXT,               -- JSON数组，帖子配图URL列表（雪球status.pic/image_info_list）
    image_desc    TEXT,                -- 视觉模型对配图的文字描述缓存，避免重复调用
    fetched_at    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_posts_user_date ON posts(user_id, date);

CREATE TABLE IF NOT EXISTS summaries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT,                 -- 大V id
    period_type TEXT,                 -- daily/weekly/monthly/yearly/highlights
    period_key  TEXT,                 -- 2026-06-30 / 2026-W26 / 2026-06 / 2026
    content     TEXT,                 -- markdown 正文
    created_at  INTEGER,
    UNIQUE(user_id, period_type, period_key)
);

CREATE TABLE IF NOT EXISTS stock_daily (
    trade_date    TEXT,               -- YYYY-MM-DD
    code          TEXT,               -- 6位股票代码
    name          TEXT,
    close         REAL,
    change_pct    REAL,               -- 涨跌幅（%）
    volume        REAL,
    amount        REAL,
    turnover_rate REAL,
    volume_ratio  REAL,
    pe_ttm        REAL,               -- 市盈率-动态
    pb            REAL,
    total_mv      REAL,
    circ_mv       REAL,
    high          REAL,
    low           REAL,
    open          REAL,
    pre_close     REAL,
    fetched_at    INTEGER,
    UNIQUE(trade_date, code)
);
CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(trade_date);

CREATE TABLE IF NOT EXISTS stock_groups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT UNIQUE,
    created_at INTEGER
);

CREATE TABLE IF NOT EXISTS stock_group_members (
    group_id   INTEGER,
    code       TEXT,
    name       TEXT,
    added_at   INTEGER,
    UNIQUE(group_id, code)
);
CREATE INDEX IF NOT EXISTS idx_group_members_group ON stock_group_members(group_id);

CREATE TABLE IF NOT EXISTS sector_catalog (
    board_code TEXT PRIMARY KEY,
    name       TEXT UNIQUE,
    kind       TEXT,               -- 'industry' | 'concept'
    updated_at INTEGER
);

CREATE TABLE IF NOT EXISTS stock_sector (
    code       TEXT,
    sector     TEXT,               -- 板块名称，对应 sector_catalog.name
    board_code TEXT,
    updated_at INTEGER,
    UNIQUE(code, sector)
);
CREATE INDEX IF NOT EXISTS idx_stock_sector_sector ON stock_sector(sector);
CREATE INDEX IF NOT EXISTS idx_stock_sector_code ON stock_sector(code);

CREATE TABLE IF NOT EXISTS stock_finance (
    code           TEXT PRIMARY KEY,
    name           TEXT,
    report_date    TEXT,               -- 报告期，如 2026-03-31
    eps            REAL,               -- 每股收益
    roe            REAL,               -- 加权平均净资产收益率(%)
    net_profit_yoy REAL,               -- 净利润同比增长率(%)
    revenue_yoy    REAL,               -- 营业收入同比增长率(%)
    gross_margin   REAL,               -- 销售毛利率(%)
    fetched_at     INTEGER
);
"""


def init_db() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate_posts_columns(conn)


def _migrate_posts_columns(conn) -> None:
    """给已存在的旧 posts 表补上新列（CREATE TABLE IF NOT EXISTS 不会给已有表加列）。"""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
    for col, ddl in (("images", "TEXT"), ("image_desc", "TEXT")):
        if col not in existing:
            conn.execute(f"ALTER TABLE posts ADD COLUMN {col} {ddl}")


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def post_exists(post_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone()
        return row is not None


def upsert_post(post: dict) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO posts
            (id, user_id, user_name, created_at, date, text, title, url,
             like_count, retweet_count, reply_count, fav_count, raw_json, images, fetched_at)
            VALUES (:id, :user_id, :user_name, :created_at, :date, :text, :title, :url,
                    :like_count, :retweet_count, :reply_count, :fav_count, :raw_json, :images, :fetched_at)
            """,
            post,
        )


def save_image_desc(post_id: str, desc: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE posts SET image_desc = ? WHERE id = ?", (desc, post_id))


def get_posts_on_date(user_id: str, date_str: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE user_id = ? AND date = ? ORDER BY created_at",
            (user_id, date_str),
        ).fetchall()
        return [dict(r) for r in rows]


def get_top_posts(user_id: str, start_date: str, end_date: str, limit: int) -> list[dict]:
    """按互动量取区间内最热帖子（含起止日）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *, (like_count + retweet_count * 2 + fav_count) AS score
            FROM posts
            WHERE user_id = ? AND date >= ? AND date <= ?
            ORDER BY score DESC, created_at DESC
            LIMIT ?
            """,
            (user_id, start_date, end_date, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_distinct_users() -> list[tuple[str, str]]:
    """返回库里已有的 (user_id, user_name)，取每人最新的昵称。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT user_id, user_name
            FROM posts p
            WHERE created_at = (
                SELECT MAX(created_at) FROM posts WHERE user_id = p.user_id
            )
            GROUP BY user_id
            """
        ).fetchall()
        return [(r["user_id"], r["user_name"]) for r in rows]


def save_summary(user_id: str, period_type: str, period_key: str, content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO summaries (user_id, period_type, period_key, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, period_type, period_key, content, int(time.time())),
        )


def get_summary(user_id: str, period_type: str, period_key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content FROM summaries WHERE user_id = ? AND period_type = ? AND period_key = ?",
            (user_id, period_type, period_key),
        ).fetchone()
        return row["content"] if row else None


def get_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM posts").fetchone()["c"]
        per_user = conn.execute(
            """
            SELECT user_name, COUNT(*) c, MIN(date) first, MAX(date) last
            FROM posts GROUP BY user_id ORDER BY c DESC
            """
        ).fetchall()
        return {"total": total, "per_user": [dict(r) for r in per_user]}


# ===== 以下供 Web 看板使用 =====
def _user_clause(user_id: str | None) -> tuple[str, list]:
    """构造可选的 user_id 过滤条件。"""
    if user_id:
        return " AND user_id = ?", [user_id]
    return "", []


def get_monthly_counts(user_id: str | None = None) -> list[dict]:
    clause, params = _user_clause(user_id)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT substr(date, 1, 7) AS ym, COUNT(*) AS n
            FROM posts WHERE date != '' {clause}
            GROUP BY ym ORDER BY ym
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_daily_counts(user_id: str | None = None, start: str = "", end: str = "") -> list[dict]:
    clause, params = _user_clause(user_id)
    extra = ""
    if start:
        extra += " AND date >= ?"
        params.append(start)
    if end:
        extra += " AND date <= ?"
        params.append(end)
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT date, COUNT(*) AS n
            FROM posts WHERE date != '' {clause} {extra}
            GROUP BY date ORDER BY date
            """,
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def get_posts(
    user_id: str | None = None,
    start: str = "",
    end: str = "",
    q: str = "",
    limit: int = 30,
    offset: int = 0,
) -> dict:
    """分页查询帖子，返回 {'total': n, 'items': [...]}。按时间倒序。"""
    clause, params = _user_clause(user_id)
    extra = ""
    if start:
        extra += " AND date >= ?"
        params.append(start)
    if end:
        extra += " AND date <= ?"
        params.append(end)
    if q:
        extra += " AND (text LIKE ? OR title LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]

    where = f"WHERE 1=1 {clause} {extra}"
    with get_conn() as conn:
        total = conn.execute(f"SELECT COUNT(*) c FROM posts {where}", params).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT id, user_name, date, created_at, title, text, url,
                   like_count, retweet_count, reply_count, fav_count
            FROM posts {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()
        return {"total": total, "items": [dict(r) for r in rows]}


def get_summary_keys(user_id: str, period_type: str) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT period_key FROM summaries
            WHERE user_id = ? AND period_type = ?
            ORDER BY period_key DESC
            """,
            (user_id, period_type),
        ).fetchall()
        return [r["period_key"] for r in rows]


# ===== 以下供选股功能使用 =====
def save_snapshot(trade_date: str, rows: list[dict]) -> int:
    """批量写入某天的全市场快照（upsert）。rows 里每个 dict 用我们自己的字段名。"""
    now = int(time.time())
    payload = [
        (
            trade_date, r.get("code"), r.get("name"), r.get("close"), r.get("change_pct"),
            r.get("volume"), r.get("amount"), r.get("turnover_rate"), r.get("volume_ratio"),
            r.get("pe_ttm"), r.get("pb"), r.get("total_mv"), r.get("circ_mv"),
            r.get("high"), r.get("low"), r.get("open"), r.get("pre_close"), now,
        )
        for r in rows
    ]
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stock_daily
            (trade_date, code, name, close, change_pct, volume, amount,
             turnover_rate, volume_ratio, pe_ttm, pb, total_mv, circ_mv,
             high, low, open, pre_close, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    return len(payload)


def get_latest_trade_date() -> str | None:
    with get_conn() as conn:
        row = conn.execute("SELECT MAX(trade_date) d FROM stock_daily").fetchone()
        return row["d"] if row and row["d"] else None


def screen_stocks(trade_date: str, where_sql: str, params: list, limit: int) -> list[dict]:
    """where_sql 形如 ' AND change_pct > ? AND pe_ttm <= ?'，字段/操作符已在上层做白名单校验。"""
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM stock_daily
            WHERE trade_date = ? {where_sql}
            ORDER BY change_pct DESC
            LIMIT ?
            """,
            [trade_date] + params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]


def get_latest_rows() -> list[dict]:
    """取最新一天的全市场快照（预设策略用来做板块/ST/停牌过滤及展示字段）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM stock_daily
            WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily)
            """
        ).fetchall()
        return [dict(r) for r in rows]


def save_history_bars(rows: list[dict]) -> int:
    """批量写入历史K线（每行自带各自的 trade_date）。用 INSERT OR IGNORE，
    避免回补的历史日期撞上已有的完整快照行时，被 NULL 字段覆盖掉；但对已存在的行，
    额外补一次 UPDATE，把仍缺失的 open 填上（不碰其它字段），这样重跑回补也能把
    旧版本回补时漏采的开盘价补齐，而不会被 INSERT OR IGNORE 直接跳过。"""
    now = int(time.time())
    payload = [
        (r.get("trade_date"), r.get("code"), r.get("name"), r.get("close"),
         r.get("high"), r.get("low"), r.get("open"), r.get("volume"), now)
        for r in rows
    ]
    open_updates = [
        (r.get("open"), r.get("trade_date"), r.get("code"))
        for r in rows if r.get("open") is not None
    ]
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO stock_daily
            (trade_date, code, name, close, high, low, open, volume, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        if open_updates:
            conn.executemany(
                "UPDATE stock_daily SET open = ? WHERE trade_date = ? AND code = ? AND open IS NULL",
                open_updates,
            )
    return len(payload)


def get_history_since(since_date: str) -> list[dict]:
    """取某天以来所有股票的历史K线（按 code, trade_date 排序，供上层按 code 分组算指标）。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT code, trade_date, close, high, low, open, volume
            FROM stock_daily
            WHERE trade_date >= ?
            ORDER BY code, trade_date
            """,
            (since_date,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_history_for_code(code: str) -> list[dict]:
    """取单只股票的全部历史K线（按 trade_date 升序），供个股详情页画图用。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT trade_date, open, high, low, close, volume
            FROM stock_daily
            WHERE code = ?
            ORDER BY trade_date
            """,
            (code,),
        ).fetchall()
        return [dict(r) for r in rows]


def save_finance(rows: list[dict]) -> int:
    """批量写入财务指标快照（upsert，主键为 code，每只股票只留最新一期）。"""
    now = int(time.time())
    payload = [
        (
            r.get("code"), r.get("name"), r.get("report_date"), r.get("eps"),
            r.get("roe"), r.get("net_profit_yoy"), r.get("revenue_yoy"), r.get("gross_margin"), now,
        )
        for r in rows
    ]
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stock_finance
            (code, name, report_date, eps, roe, net_profit_yoy, revenue_yoy, gross_margin, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    return len(payload)


def get_finance_map() -> dict[str, dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM stock_finance").fetchall()
        return {r["code"]: dict(r) for r in rows}


def get_finance_by_code(code: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM stock_finance WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None


def search_posts_containing(terms: list[str], since_date: str, limit: int = 200) -> list[dict]:
    """按关键词（OR）在 text/title 里做 LIKE 粗筛，返回最近的帖子详情，供个股详情页
    「大V提及」反查使用（精确判断——是否真的是这只股票——交给上层的 TICKER_RE/名称匹配）。"""
    terms = [t for t in terms if t]
    if not terms:
        return []
    clauses = " OR ".join(["(text LIKE ? OR title LIKE ?)"] * len(terms))
    params: list = []
    for t in terms:
        params += [f"%{t}%", f"%{t}%"]
    with get_conn() as conn:
        rows = conn.execute(
            f"""
            SELECT id, user_name, date, title, text, url, like_count, retweet_count, reply_count, fav_count
            FROM posts
            WHERE date >= ? AND ({clauses})
            ORDER BY created_at DESC
            LIMIT ?
            """,
            [since_date] + params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_texts(user_ids: list[str], days: int) -> list[tuple[str, str]]:
    """返回指定大V最近 N 天的 (user_id, text)，供大V提及匹配使用。"""
    if not user_ids:
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    placeholders = ",".join("?" for _ in user_ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT user_id, text FROM posts WHERE date >= ? AND user_id IN ({placeholders})",
            [cutoff] + list(user_ids),
        ).fetchall()
        return [(r["user_id"], r["text"] or "") for r in rows]


# ===== 以下供股票分组（自选股组）使用 =====
def create_group(name: str) -> int | None:
    """新建分组，重名返回 None。"""
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO stock_groups (name, created_at) VALUES (?, ?)",
                (name, int(time.time())),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def delete_group(group_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM stock_group_members WHERE group_id = ?", (group_id,))
        conn.execute("DELETE FROM stock_groups WHERE id = ?", (group_id,))


def list_groups() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.name, g.created_at, COUNT(m.code) AS member_count
            FROM stock_groups g
            LEFT JOIN stock_group_members m ON m.group_id = g.id
            GROUP BY g.id
            ORDER BY g.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def add_group_members(group_id: int, stocks: list[dict]) -> int:
    """stocks: [{'code':..., 'name':...}, ...]；已在组内的自动忽略。"""
    now = int(time.time())
    payload = [(group_id, s.get("code"), s.get("name"), now) for s in stocks if s.get("code")]
    if not payload:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO stock_group_members (group_id, code, name, added_at)
            VALUES (?, ?, ?, ?)
            """,
            payload,
        )
    return len(payload)


def remove_group_member(group_id: int, code: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM stock_group_members WHERE group_id = ? AND code = ?",
            (group_id, code),
        )


def get_group_members(group_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT code, name, added_at FROM stock_group_members WHERE group_id = ? ORDER BY added_at DESC",
            (group_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ===== 以下供板块（行业/概念）筛选使用 =====
def save_sector_catalog(rows: list[dict]) -> int:
    """rows: [{'board_code':..., 'name':..., 'kind':...}, ...]。"""
    now = int(time.time())
    payload = [(r["board_code"], r["name"], r["kind"], now) for r in rows if r.get("board_code") and r.get("name")]
    if not payload:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO sector_catalog (board_code, name, kind, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            payload,
        )
    return len(payload)


def get_sector_catalog() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT board_code, name, kind FROM sector_catalog ORDER BY kind, name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_board_code(name: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT board_code FROM sector_catalog WHERE name = ?", (name,)
        ).fetchone()
        return row["board_code"] if row else None


def get_sector_members_cached(sector: str, max_age_days: int = 7) -> list[str] | None:
    """命中且未过期返回股票代码列表；未缓存或已过期返回 None，交由上层重新拉取。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT updated_at FROM stock_sector WHERE sector = ? ORDER BY updated_at DESC LIMIT 1",
            (sector,),
        ).fetchone()
        if not row:
            return None
        if int(time.time()) - row["updated_at"] > max_age_days * 86400:
            return None
        codes = conn.execute(
            "SELECT code FROM stock_sector WHERE sector = ?", (sector,)
        ).fetchall()
        return [r["code"] for r in codes]


def save_sector_members(sector: str, board_code: str, codes: list[str]) -> int:
    now = int(time.time())
    with get_conn() as conn:
        conn.execute("DELETE FROM stock_sector WHERE sector = ?", (sector,))
        payload = [(c, sector, board_code, now) for c in codes if c]
        if payload:
            conn.executemany(
                """
                INSERT OR IGNORE INTO stock_sector (code, sector, board_code, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                payload,
            )
    return len(payload)


def get_sectors_by_code(code: str) -> list[dict]:
    """反查某只股票所属的板块（行业+概念），供个股详情页展示。依赖 stock_sector 缓存，
    覆盖率取决于哪些板块已被筛选/同步过——完整展示需先跑一次全量成分股同步。"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.sector, s.board_code, c.kind
            FROM stock_sector s
            LEFT JOIN sector_catalog c ON c.name = s.sector
            WHERE s.code = ?
            ORDER BY c.kind, s.sector
            """,
            (code,),
        ).fetchall()
        return [dict(r) for r in rows]
