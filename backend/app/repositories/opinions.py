"""Synchronous persistence for structured article claims."""
import time

from sqlalchemy import text

from app.core.sync_db import sync_session


def replace_claims(post_id: str, claims: list[dict], raw_json: str = "") -> int:
    now = int(time.time())
    with sync_session() as session:
        session.execute(text("DELETE FROM opinion_claims WHERE post_id = :post_id"), {"post_id": post_id})
        if claims:
            session.execute(text("""
                INSERT INTO opinion_claims
                    (post_id, code, name, direction, claim, evidence, confidence, status, error, raw_json, created_at, updated_at)
                VALUES
                    (:post_id, :code, :name, :direction, :claim, :evidence, :confidence, 'ready', NULL, :raw_json, :created_at, :updated_at)
            """), [{
                "post_id": post_id,
                "code": item.get("code"), "name": item.get("name"),
                "direction": item.get("direction") or "未定向",
                "claim": item.get("claim"), "evidence": item.get("evidence"),
                "confidence": item.get("confidence"), "raw_json": raw_json,
                "created_at": now, "updated_at": now,
            } for item in claims])
    return len(claims)


def mark_pending(post_id: str) -> None:
    now = int(time.time())
    with sync_session() as session:
        session.execute(text("""
            INSERT INTO opinion_claims (post_id, direction, status, created_at, updated_at)
            VALUES (:post_id, '未定向', 'pending', :now, :now)
            ON CONFLICT DO NOTHING
        """), {"post_id": post_id, "now": now})


def mark_error(post_id: str, error: str) -> None:
    now = int(time.time())
    with sync_session() as session:
        session.execute(text("DELETE FROM opinion_claims WHERE post_id = :post_id"), {"post_id": post_id})
        session.execute(text("""
            INSERT INTO opinion_claims (post_id, direction, status, error, created_at, updated_at)
            VALUES (:post_id, '未定向', 'error', :error, :now, :now)
        """), {"post_id": post_id, "error": error[:2000], "now": now})


def get_claims(post_ids: list[str]) -> dict[str, list[dict]]:
    if not post_ids:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(post_ids)))
    with sync_session() as session:
        rows = session.execute(text(f"""
            SELECT post_id, code, name, direction, claim, evidence, confidence, status, error
            FROM opinion_claims
            WHERE post_id IN ({placeholders})
            ORDER BY id
        """), {f"p{i}": value for i, value in enumerate(post_ids)}).mappings().all()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["post_id"], []).append(dict(row))
    return result
