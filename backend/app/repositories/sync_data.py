"""同步数据访问层：忠实移植旧 db.py 中「选股/K线/基本面」服务所需的读写函数。

设计与旧 db.py 一致——每个函数开一个短会话（原来是 with get_conn()）。返回 dict 的键与
旧 sqlite3.Row 完全一致，使 ported stock.py 逻辑可近乎逐字复用。仅供 run_in_threadpool
里的同步计算路径使用；轻量读接口请走 app/repositories/*.py 的异步仓储。
"""
import time

from sqlalchemy import text

from app.core.sync_db import sync_session


def get_distinct_users() -> list[tuple[str, str]]:
    with sync_session() as s:
        rows = s.execute(text(
            """
            SELECT user_id, user_name
            FROM posts p
            WHERE created_at = (SELECT MAX(created_at) FROM posts WHERE user_id = p.user_id)
            GROUP BY user_id, user_name
            """
        )).all()
        return [(r[0], r[1]) for r in rows]


def get_latest_trade_date() -> str | None:
    with sync_session() as s:
        return s.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()


def get_latest_rows() -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            "SELECT * FROM stock_daily WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily)"
        )).mappings().all()
        return [dict(r) for r in rows]


def screen_stocks(trade_date: str, where_sql: str, params: dict, limit: int) -> list[dict]:
    """where_sql 形如 ' AND change_pct > :p0 AND pe_ttm <= :p1'（字段/操作符已在上层白名单校验）。"""
    with sync_session() as s:
        rows = s.execute(text(
            f"""
            SELECT * FROM stock_daily
            WHERE trade_date = :trade_date {where_sql}
            ORDER BY change_pct DESC NULLS LAST
            LIMIT :limit
            """
        ), {"trade_date": trade_date, "limit": limit, **params}).mappings().all()
        return [dict(r) for r in rows]


def get_history_since(since_date: str) -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            """
            SELECT code, trade_date, close, high, low, open, volume
            FROM stock_daily
            WHERE trade_date >= :since
            ORDER BY code, trade_date
            """
        ), {"since": since_date}).mappings().all()
        return [dict(r) for r in rows]


def get_history_for_code(code: str) -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            """
            SELECT trade_date, open, high, low, close, volume
            FROM stock_daily
            WHERE code = :code
            ORDER BY trade_date
            """
        ), {"code": code}).mappings().all()
        return [dict(r) for r in rows]


def get_finance_map() -> dict[str, dict]:
    with sync_session() as s:
        rows = s.execute(text("SELECT * FROM stock_finance")).mappings().all()
        return {r["code"]: dict(r) for r in rows}


def get_finance_by_code(code: str) -> dict | None:
    with sync_session() as s:
        row = s.execute(text("SELECT * FROM stock_finance WHERE code = :c"), {"c": code}).mappings().first()
        return dict(row) if row else None


def search_posts_containing(terms: list[str], since_date: str, limit: int = 200) -> list[dict]:
    terms = [t for t in terms if t]
    if not terms:
        return []
    clauses = []
    params: dict = {"since": since_date, "limit": limit}
    for i, t in enumerate(terms):
        clauses.append(f"(text LIKE :t{i} OR title LIKE :t{i})")
        params[f"t{i}"] = f"%{t}%"
    where = " OR ".join(clauses)
    with sync_session() as s:
        rows = s.execute(text(
            f"""
            SELECT id, user_name, date, title, text, url, like_count, retweet_count, reply_count, fav_count
            FROM posts
            WHERE date >= :since AND ({where})
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ), params).mappings().all()
        return [dict(r) for r in rows]


def get_recent_texts(user_ids: list[str], days: int) -> list[tuple[str, str]]:
    from datetime import date, timedelta
    if not user_ids:
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    params: dict = {"cutoff": cutoff}
    ph = []
    for i, uid in enumerate(user_ids):
        ph.append(f":u{i}")
        params[f"u{i}"] = uid
    with sync_session() as s:
        rows = s.execute(text(
            f"SELECT user_id, text FROM posts WHERE date >= :cutoff AND user_id IN ({', '.join(ph)})"
        ), params).all()
        return [(r[0], r[1] or "") for r in rows]


def get_sector_catalog() -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            "SELECT board_code, name, kind FROM sector_catalog ORDER BY kind, name"
        )).mappings().all()
        return [dict(r) for r in rows]


def get_board_code(name: str) -> str | None:
    with sync_session() as s:
        return s.execute(text("SELECT board_code FROM sector_catalog WHERE name = :n"), {"n": name}).scalar()


def get_sector_members_cached(sector: str, max_age_days: int = 7) -> list[str] | None:
    with sync_session() as s:
        row = s.execute(text(
            "SELECT updated_at FROM stock_sector WHERE sector = :s ORDER BY updated_at DESC LIMIT 1"
        ), {"s": sector}).first()
        if not row:
            return None
        if int(time.time()) - (row[0] or 0) > max_age_days * 86400:
            return None
        codes = s.execute(text("SELECT code FROM stock_sector WHERE sector = :s"), {"s": sector}).all()
        return [c[0] for c in codes]


def save_sector_members(sector: str, board_code: str, codes: list[str]) -> int:
    now = int(time.time())
    with sync_session() as s:
        s.execute(text("DELETE FROM stock_sector WHERE sector = :s"), {"s": sector})
        payload = [{"code": c, "sector": sector, "board_code": board_code, "updated_at": now}
                   for c in codes if c]
        if payload:
            s.execute(text(
                """
                INSERT INTO stock_sector (code, sector, board_code, updated_at)
                VALUES (:code, :sector, :board_code, :updated_at)
                ON CONFLICT (code, sector) DO NOTHING
                """
            ), payload)
        return len(payload)


def save_xueqiu_sectors(items: list[dict]) -> tuple[int, int]:
    """写入雪球板块抓取结果：先落 sector_catalog（供 save_sector_catalog 处理撞名跳过），
    再对每个真正落地的行业落 stock_sector 成分股（沿用 save_sector_members 的整体替换语义）。
    items 形如 [{"board_code": "xq_S2701", "name": "半导体", "kind": "industry", "codes": [...]}, ...]。
    返回 (落地的行业数, 成分股关系总数)。
    """
    saved_names = save_sector_catalog([
        {"board_code": it["board_code"], "name": it["name"], "kind": it["kind"]} for it in items
    ])
    if not saved_names:
        return 0, 0
    with sync_session() as s:
        landed = {row[0] for row in s.execute(text(
            "SELECT name FROM sector_catalog WHERE board_code = ANY(:codes)"
        ), {"codes": [it["board_code"] for it in items]}).all()}
    n_sectors = 0
    n_codes = 0
    for it in items:
        if it["name"] not in landed:
            continue  # 撞名被跳过，不写成分股（避免覆盖已有同名板块的成分股关系）
        n = save_sector_members(it["name"], it["board_code"], it.get("codes") or [])
        n_sectors += 1
        n_codes += n
    return n_sectors, n_codes


def get_sectors_by_code(code: str) -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            """
            SELECT s.sector, s.board_code, c.kind
            FROM stock_sector s
            LEFT JOIN sector_catalog c ON c.name = s.sector
            WHERE s.code = :code
            ORDER BY c.kind, s.sector
            """
        ), {"code": code}).mappings().all()
        return [dict(r) for r in rows]


def get_group_members(group_id: int) -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            "SELECT code, name, added_at FROM stock_group_members WHERE group_id = :g ORDER BY added_at DESC"
        ), {"g": group_id}).mappings().all()
        return [dict(r) for r in rows]


# ===== 预计算指标（Phase 5）=====
def get_indicator_map() -> dict[str, dict]:
    with sync_session() as s:
        rows = s.execute(text("SELECT * FROM stock_indicator")).mappings().all()
        return {r["code"]: dict(r) for r in rows}


def indicator_trade_date() -> str | None:
    """预计算表所依据的交易日（取任一行的 trade_date；全表同一天）。"""
    with sync_session() as s:
        return s.execute(text("SELECT MAX(trade_date) FROM stock_indicator")).scalar()


def save_indicators(trade_date: str, rows: list[dict]) -> int:
    """全量重算后落库：先清空再批量写（一次数据版本一张全量快照，避免残留旧代码）。"""
    now = int(time.time())
    payload = [{
        "code": r["code"], "trade_date": trade_date,
        "ma5": r.get("ma5"), "ma10": r.get("ma10"), "ma20": r.get("ma20"),
        "cross1": bool(r.get("cross1")), "cross23": bool(r.get("cross23")),
        "rise5": bool(r.get("rise5")), "price_above20": bool(r.get("price_above20")),
        "duotou": bool(r.get("duotou")), "macd_recent": bool(r.get("macd_recent")),
        "kdj_recent": bool(r.get("kdj_recent")), "updated_at": now,
    } for r in rows if r.get("code")]
    with sync_session() as s:
        s.execute(text("DELETE FROM stock_indicator"))
        if payload:
            s.execute(text(
                """
                INSERT INTO stock_indicator
                (code, trade_date, ma5, ma10, ma20, cross1, cross23, rise5, price_above20,
                 duotou, macd_recent, kdj_recent, updated_at)
                VALUES (:code, :trade_date, :ma5, :ma10, :ma20, :cross1, :cross23, :rise5,
                        :price_above20, :duotou, :macd_recent, :kdj_recent, :updated_at)
                """
            ), payload)
    return len(payload)


# ==========================================================================
# 写函数（Phase 2 worker / 管理员接口用）。旧 db.py 的 INSERT OR REPLACE/IGNORE
# 一律翻译为 Postgres ON CONFLICT。executemany 通过给 execute 传 dict 列表实现。
# ==========================================================================

def post_exists(post_id: str) -> bool:
    with sync_session() as s:
        return s.execute(text("SELECT 1 FROM posts WHERE id = :id"), {"id": post_id}).first() is not None


def upsert_post(post: dict) -> None:
    """INSERT OR REPLACE 语义（PK id）。不写 image_desc（由 save_image_desc 单独维护）。"""
    with sync_session() as s:
        s.execute(text(
            """
            INSERT INTO posts
            (id, user_id, user_name, created_at, date, text, title, url,
             like_count, retweet_count, reply_count, fav_count, raw_json, images, fetched_at)
            VALUES (:id, :user_id, :user_name, :created_at, :date, :text, :title, :url,
                    :like_count, :retweet_count, :reply_count, :fav_count, :raw_json, :images, :fetched_at)
            ON CONFLICT (id) DO UPDATE SET
                user_id=EXCLUDED.user_id, user_name=EXCLUDED.user_name, created_at=EXCLUDED.created_at,
                date=EXCLUDED.date, text=EXCLUDED.text, title=EXCLUDED.title, url=EXCLUDED.url,
                like_count=EXCLUDED.like_count, retweet_count=EXCLUDED.retweet_count,
                reply_count=EXCLUDED.reply_count, fav_count=EXCLUDED.fav_count,
                raw_json=EXCLUDED.raw_json, images=EXCLUDED.images, fetched_at=EXCLUDED.fetched_at
            """
        ), post)


def save_image_desc(post_id: str, desc: str) -> None:
    with sync_session() as s:
        s.execute(text("UPDATE posts SET image_desc = :d WHERE id = :id"), {"d": desc, "id": post_id})


def get_posts_on_date(user_id: str, date_str: str) -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            "SELECT * FROM posts WHERE user_id = :u AND date = :d ORDER BY created_at"
        ), {"u": user_id, "d": date_str}).mappings().all()
        return [dict(r) for r in rows]


def get_top_posts(user_id: str, start_date: str, end_date: str, limit: int) -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            """
            SELECT *, (like_count + retweet_count * 2 + fav_count) AS score
            FROM posts
            WHERE user_id = :u AND date >= :start AND date <= :end
            ORDER BY score DESC, created_at DESC
            LIMIT :limit
            """
        ), {"u": user_id, "start": start_date, "end": end_date, "limit": limit}).mappings().all()
        return [dict(r) for r in rows]


def get_recent_daily_summaries(user_ids: list[str], days: int) -> list[str]:
    """最近 N 天的"日总结"markdown 正文（period_key 是 ISO 日期，字符串比较即可），供选股"只看看多"解析。"""
    from datetime import date, timedelta
    if not user_ids:
        return []
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    params: dict = {"cutoff": cutoff}
    ph = []
    for i, uid in enumerate(user_ids):
        ph.append(f":u{i}")
        params[f"u{i}"] = uid
    with sync_session() as s:
        rows = s.execute(text(
            f"""
            SELECT content FROM summaries
            WHERE period_type = 'daily' AND period_key >= :cutoff AND user_id IN ({', '.join(ph)})
            """
        ), params).all()
        return [r[0] for r in rows if r[0]]


def get_summary(user_id: str, period_type: str, period_key: str) -> str | None:
    with sync_session() as s:
        row = s.execute(text(
            "SELECT content FROM summaries WHERE user_id = :u AND period_type = :t AND period_key = :k"
        ), {"u": user_id, "t": period_type, "k": period_key}).first()
        return row[0] if row else None


def save_summary(user_id: str, period_type: str, period_key: str, content: str) -> None:
    with sync_session() as s:
        s.execute(text(
            """
            INSERT INTO summaries (user_id, period_type, period_key, content, created_at)
            VALUES (:u, :t, :k, :c, :now)
            ON CONFLICT (user_id, period_type, period_key) DO UPDATE SET
                content=EXCLUDED.content, created_at=EXCLUDED.created_at
            """
        ), {"u": user_id, "t": period_type, "k": period_key, "c": content, "now": int(time.time())})


def save_snapshot(trade_date: str, rows: list[dict]) -> int:
    now = int(time.time())
    payload = [{
        "trade_date": trade_date, "code": r.get("code"), "name": r.get("name"),
        "close": r.get("close"), "change_pct": r.get("change_pct"), "volume": r.get("volume"),
        "amount": r.get("amount"), "turnover_rate": r.get("turnover_rate"),
        "volume_ratio": r.get("volume_ratio"), "pe_ttm": r.get("pe_ttm"), "pb": r.get("pb"),
        "total_mv": r.get("total_mv"), "circ_mv": r.get("circ_mv"), "high": r.get("high"),
        "low": r.get("low"), "open": r.get("open"), "pre_close": r.get("pre_close"), "fetched_at": now,
    } for r in rows]
    if not payload:
        return 0
    with sync_session() as s:
        s.execute(text(
            """
            INSERT INTO stock_daily
            (trade_date, code, name, close, change_pct, volume, amount, turnover_rate, volume_ratio,
             pe_ttm, pb, total_mv, circ_mv, high, low, open, pre_close, fetched_at)
            VALUES (:trade_date, :code, :name, :close, :change_pct, :volume, :amount, :turnover_rate,
                    :volume_ratio, :pe_ttm, :pb, :total_mv, :circ_mv, :high, :low, :open, :pre_close, :fetched_at)
            ON CONFLICT (trade_date, code) DO UPDATE SET
                name=EXCLUDED.name, close=EXCLUDED.close, change_pct=EXCLUDED.change_pct,
                volume=EXCLUDED.volume, amount=EXCLUDED.amount, turnover_rate=EXCLUDED.turnover_rate,
                volume_ratio=EXCLUDED.volume_ratio, pe_ttm=EXCLUDED.pe_ttm, pb=EXCLUDED.pb,
                total_mv=EXCLUDED.total_mv, circ_mv=EXCLUDED.circ_mv, high=EXCLUDED.high,
                low=EXCLUDED.low, open=EXCLUDED.open, pre_close=EXCLUDED.pre_close, fetched_at=EXCLUDED.fetched_at
            """
        ), payload)
    return len(payload)


def save_history_bars(rows: list[dict]) -> int:
    """冲突时整行覆盖 OHLC/volume（不再是"只补空 open"）。

    改成整行覆盖是必要的：现在 kline.py 回补前会用复权因子调整 open/high/low/close，同一天
    的调整结果会随着后续新的除权事件而变化（前复权本质上是"越早的历史越会被未来的分红改写"），
    重新回补同一时间窗口必须能真正覆盖旧值，而不是只在 open 为空时才补一次就再也不动。
    """
    now = int(time.time())
    payload = [{
        "trade_date": r.get("trade_date"), "code": r.get("code"), "name": r.get("name"),
        "close": r.get("close"), "high": r.get("high"), "low": r.get("low"),
        "open": r.get("open"), "volume": r.get("volume"), "fetched_at": now,
    } for r in rows]
    if not payload:
        return 0
    with sync_session() as s:
        s.execute(text(
            """
            INSERT INTO stock_daily
            (trade_date, code, name, close, high, low, open, volume, fetched_at)
            VALUES (:trade_date, :code, :name, :close, :high, :low, :open, :volume, :fetched_at)
            ON CONFLICT (trade_date, code) DO UPDATE SET
                close = EXCLUDED.close, high = EXCLUDED.high, low = EXCLUDED.low,
                open = EXCLUDED.open, volume = EXCLUDED.volume, fetched_at = EXCLUDED.fetched_at
            """
        ), payload)
    return len(payload)


def save_finance(rows: list[dict]) -> int:
    now = int(time.time())
    payload = [{
        "code": r.get("code"), "name": r.get("name"), "report_date": r.get("report_date"),
        "eps": r.get("eps"), "roe": r.get("roe"), "net_profit_yoy": r.get("net_profit_yoy"),
        "revenue_yoy": r.get("revenue_yoy"), "gross_margin": r.get("gross_margin"), "fetched_at": now,
    } for r in rows]
    if not payload:
        return 0
    with sync_session() as s:
        s.execute(text(
            """
            INSERT INTO stock_finance
            (code, name, report_date, eps, roe, net_profit_yoy, revenue_yoy, gross_margin, fetched_at)
            VALUES (:code, :name, :report_date, :eps, :roe, :net_profit_yoy, :revenue_yoy, :gross_margin, :fetched_at)
            ON CONFLICT (code) DO UPDATE SET
                name=EXCLUDED.name, report_date=EXCLUDED.report_date, eps=EXCLUDED.eps, roe=EXCLUDED.roe,
                net_profit_yoy=EXCLUDED.net_profit_yoy, revenue_yoy=EXCLUDED.revenue_yoy,
                gross_margin=EXCLUDED.gross_margin, fetched_at=EXCLUDED.fetched_at
            """
        ), payload)
    return len(payload)


def save_sector_catalog(rows: list[dict]) -> int:
    """`name` 有唯一约束（选股页按板块名而非 board_code 筛选）；不同来源撞名时保留已有的那条，
    跳过新来源的同名行——目前已知雪球行业与新浪行业有5个重名（教育/体育/渔业/林业/综合）。
    """
    now = int(time.time())
    payload = [{"board_code": r["board_code"], "name": r["name"], "kind": r["kind"], "updated_at": now}
               for r in rows if r.get("board_code") and r.get("name")]
    if not payload:
        return 0
    with sync_session() as s:
        existing = {
            row[0] for row in s.execute(text(
                "SELECT name FROM sector_catalog WHERE board_code != ANY(:codes)"
            ), {"codes": [p["board_code"] for p in payload]}).all()
        }
        payload = [p for p in payload if p["name"] not in existing]
        if not payload:
            return 0
        s.execute(text(
            """
            INSERT INTO sector_catalog (board_code, name, kind, updated_at)
            VALUES (:board_code, :name, :kind, :updated_at)
            ON CONFLICT (board_code) DO UPDATE SET
                name=EXCLUDED.name, kind=EXCLUDED.kind, updated_at=EXCLUDED.updated_at
            """
        ), payload)
    return len(payload)


# ===== 分组写 =====
def create_group(name: str) -> int | None:
    with sync_session() as s:
        row = s.execute(text(
            """
            INSERT INTO stock_groups (name, created_at) VALUES (:n, :now)
            ON CONFLICT (name) DO NOTHING
            RETURNING id
            """
        ), {"n": name, "now": int(time.time())}).first()
        return row[0] if row else None


def delete_group(group_id: int) -> None:
    with sync_session() as s:
        s.execute(text("DELETE FROM stock_group_members WHERE group_id = :g"), {"g": group_id})
        s.execute(text("DELETE FROM stock_groups WHERE id = :g"), {"g": group_id})


def add_group_members(group_id: int, stocks: list[dict]) -> int:
    now = int(time.time())
    payload = [{"g": group_id, "code": s2.get("code"), "name": s2.get("name"), "now": now}
               for s2 in stocks if s2.get("code")]
    if not payload:
        return 0
    with sync_session() as s:
        s.execute(text(
            """
            INSERT INTO stock_group_members (group_id, code, name, added_at)
            VALUES (:g, :code, :name, :now)
            ON CONFLICT (group_id, code) DO NOTHING
            """
        ), payload)
    return len(payload)


def remove_group_member(group_id: int, code: str) -> None:
    with sync_session() as s:
        s.execute(text(
            "DELETE FROM stock_group_members WHERE group_id = :g AND code = :c"
        ), {"g": group_id, "c": code})


def list_groups() -> list[dict]:
    with sync_session() as s:
        rows = s.execute(text(
            """
            SELECT g.id, g.name, g.created_at, COUNT(m.code) AS member_count
            FROM stock_groups g
            LEFT JOIN stock_group_members m ON m.group_id = g.id
            GROUP BY g.id, g.name, g.created_at
            ORDER BY g.created_at DESC
            """
        )).mappings().all()
        return [dict(r) for r in rows]


# ===== 采集名单 / 定时配置 =====
def get_enabled_xueqiu_users() -> list[str]:
    """返回启用的大V采集标识（user_id 字段，可能是 uid / url / 昵称，与旧 XUEQIU_USERS 语义一致）。"""
    with sync_session() as s:
        rows = s.execute(text(
            "SELECT user_id FROM xueqiu_users WHERE enabled = TRUE ORDER BY id"
        )).all()
        return [r[0] for r in rows]


def get_schedule() -> dict:
    with sync_session() as s:
        row = s.execute(text(
            'SELECT enabled, start, "end", interval, stock_auto_sync_enabled, weekly_summary_enabled '
            "FROM schedules ORDER BY id LIMIT 1"
        )).mappings().first()
        if not row:
            return {
                "enabled": False, "start": "08:00", "end": "22:00", "interval": 30,
                "stock_auto_sync_enabled": True, "weekly_summary_enabled": True,
            }
        return dict(row)


def save_schedule(cfg: dict) -> dict:
    now = int(time.time())
    with sync_session() as s:
        existing = s.execute(text("SELECT id FROM schedules ORDER BY id LIMIT 1")).first()
        params = {
            "enabled": bool(cfg.get("enabled", False)),
            "start": str(cfg.get("start", "08:00")),
            "end": str(cfg.get("end", "22:00")),
            "interval": max(5, int(cfg.get("interval", 30) or 30)),
            "stock_auto_sync_enabled": bool(cfg.get("stock_auto_sync_enabled", True)),
            "weekly_summary_enabled": bool(cfg.get("weekly_summary_enabled", True)),
            "now": now,
        }
        if existing:
            params["id"] = existing[0]
            s.execute(text(
                'UPDATE schedules SET enabled=:enabled, start=:start, "end"=:end, '
                "interval=:interval, stock_auto_sync_enabled=:stock_auto_sync_enabled, "
                "weekly_summary_enabled=:weekly_summary_enabled, updated_at=:now WHERE id=:id"
            ), params)
        else:
            s.execute(text(
                'INSERT INTO schedules (enabled, start, "end", interval, '
                "stock_auto_sync_enabled, weekly_summary_enabled, updated_at) "
                "VALUES (:enabled, :start, :end, :interval, "
                ":stock_auto_sync_enabled, :weekly_summary_enabled, :now)"
            ), params)
    return {k: params[k] for k in (
        "enabled", "start", "end", "interval", "stock_auto_sync_enabled", "weekly_summary_enabled",
    )}
