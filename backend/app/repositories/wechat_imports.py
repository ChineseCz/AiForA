"""Persistence for individual WeChat article import attempts."""
import time
from sqlalchemy import text
from app.core.sync_db import sync_session


def register_urls(urls: list[str]) -> None:
    now = int(time.time())
    with sync_session() as session:
        session.execute(text("""
            INSERT INTO wechat_import_items (url, status, attempts, created_at, updated_at)
            VALUES (:url, 'pending', 0, :now, :now)
            ON CONFLICT (url) DO UPDATE SET status = 'pending', error = NULL, updated_at = :now
        """), [{"url": url, "now": now} for url in urls])


def mark_started(url: str) -> None:
    with sync_session() as session:
        session.execute(text("""
            UPDATE wechat_import_items
            SET status = 'running', attempts = attempts + 1, error = NULL, updated_at = :now
            WHERE url = :url
        """), {"url": url, "now": int(time.time())})


def mark_success(url: str, post_id: str, title: str) -> None:
    with sync_session() as session:
        session.execute(text("""
            UPDATE wechat_import_items
            SET status = 'success', post_id = :post_id, title = :title, error = NULL, updated_at = :now
            WHERE url = :url
        """), {"url": url, "post_id": post_id, "title": title, "now": int(time.time())})


def mark_error(url: str, error: str) -> None:
    with sync_session() as session:
        session.execute(text("""
            UPDATE wechat_import_items
            SET status = 'error', error = :error, updated_at = :now
            WHERE url = :url
        """), {"url": url, "error": error[:2000], "now": int(time.time())})


def get_items(limit: int = 200) -> list[dict]:
    with sync_session() as session:
        rows = session.execute(text("""
            SELECT id, url, post_id, title, status, error, attempts, created_at, updated_at
            FROM wechat_import_items ORDER BY updated_at DESC, id DESC LIMIT :limit
        """), {"limit": max(1, min(limit, 500))}).mappings().all()
    return [dict(row) for row in rows]


def get_summary() -> dict:
    with sync_session() as session:
        rows = session.execute(text("SELECT status, COUNT(*) FROM wechat_import_items GROUP BY status")).all()
    counts = {row[0]: row[1] for row in rows}
    return {"total": sum(counts.values()), "pending": counts.get("pending", 0), "running": counts.get("running", 0), "success": counts.get("success", 0), "error": counts.get("error", 0)}
