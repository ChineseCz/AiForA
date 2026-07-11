"""帖子相关的异步读仓储（对应旧 db.py 的读函数，返回 dict 键与原来完全一致）。"""
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _parse_images(raw: str | None) -> list[str]:
    try:
        urls = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    # 迁移自旧库的部分行把多个 URL 用逗号拼成了一个字符串再塞进数组（旧格式遗留），拆开兜底
    out: list[str] = []
    for u in urls:
        if isinstance(u, str) and "," in u:
            out.extend(u.split(","))
        else:
            out.append(u)
    return out


async def get_distinct_users(session: AsyncSession) -> list[dict]:
    """库里已有的 (user_id, user_name)，取每人最新昵称。返回 [{'id','name'}]（供 /api/users）。

    DISTINCT ON 一次排序取「每用户最新一行」，避免相关子查询逐行重扫 posts（同款修复见
    sync_data.py::get_distinct_users，那份是给选股用的同步版本，这里是异步版本，各自维护）。
    """
    rows = (await session.execute(text(
        """
        SELECT DISTINCT ON (user_id) user_id, user_name
        FROM posts
        ORDER BY user_id, created_at DESC
        """
    ))).mappings().all()
    return [{"id": r["user_id"], "name": r["user_name"]} for r in rows]


async def get_stats(session: AsyncSession) -> dict:
    total = (await session.execute(text("SELECT COUNT(*) c FROM posts"))).scalar_one()
    per_user = (await session.execute(text(
        """
        SELECT user_name, COUNT(*) c, MIN(date) first, MAX(date) last
        FROM posts GROUP BY user_id, user_name ORDER BY c DESC
        """
    ))).mappings().all()
    return {"total": total, "per_user": [dict(r) for r in per_user]}


def _user_clause(user_id: str | None) -> tuple[str, dict]:
    if user_id:
        return " AND user_id = :user_id", {"user_id": user_id}
    return "", {}


async def get_monthly_counts(session: AsyncSession, user_id: str | None = None) -> list[dict]:
    clause, params = _user_clause(user_id)
    rows = (await session.execute(text(
        f"""
        SELECT substr(date, 1, 7) AS ym, COUNT(*) AS n
        FROM posts WHERE date != '' {clause}
        GROUP BY ym ORDER BY ym
        """
    ), params)).mappings().all()
    return [dict(r) for r in rows]


async def get_daily_counts(
    session: AsyncSession, user_id: str | None = None, start: str = "", end: str = ""
) -> list[dict]:
    clause, params = _user_clause(user_id)
    extra = ""
    if start:
        extra += " AND date >= :start"
        params["start"] = start
    if end:
        extra += " AND date <= :end"
        params["end"] = end
    rows = (await session.execute(text(
        f"""
        SELECT date, COUNT(*) AS n
        FROM posts WHERE date != '' {clause} {extra}
        GROUP BY date ORDER BY date
        """
    ), params)).mappings().all()
    return [dict(r) for r in rows]


async def get_posts(
    session: AsyncSession,
    user_id: str | None = None,
    start: str = "",
    end: str = "",
    q: str = "",
    limit: int = 30,
    offset: int = 0,
) -> dict:
    """分页查询帖子，返回 {'total': n, 'items': [...]}，按时间倒序。"""
    clause, params = _user_clause(user_id)
    extra = ""
    if start:
        extra += " AND date >= :start"
        params["start"] = start
    if end:
        extra += " AND date <= :end"
        params["end"] = end
    if q:
        extra += " AND (text LIKE :q OR title LIKE :q)"
        params["q"] = f"%{q}%"

    where = f"WHERE 1=1 {clause} {extra}"
    total = (await session.execute(
        text(f"SELECT COUNT(*) c FROM posts {where}"), params
    )).scalar_one()
    rows = (await session.execute(text(
        f"""
        SELECT id, user_name, date, created_at, title, text, url,
               like_count, retweet_count, reply_count, fav_count, images
        FROM posts {where}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """
    ), {**params, "limit": limit, "offset": offset})).mappings().all()
    items = []
    for r in rows:
        d = dict(r)
        d["images"] = _parse_images(d.get("images"))
        items.append(d)
    return {"total": total, "items": items}
