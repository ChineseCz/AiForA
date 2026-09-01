"""Synchronous persistence for structured article claims."""
import json
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
        session.execute(text("DELETE FROM bigv_review_snapshots WHERE post_id = :post_id"), {"post_id": post_id})
    return len(claims)


def mark_pending(post_id: str) -> None:
    now = int(time.time())
    with sync_session() as session:
        session.execute(text("""
            INSERT INTO opinion_claims (post_id, direction, status, created_at, updated_at)
            VALUES (:post_id, '未定向', 'pending', :now, :now)
            ON CONFLICT DO NOTHING
        """), {"post_id": post_id, "now": now})
        session.execute(text("DELETE FROM bigv_review_snapshots WHERE post_id = :post_id"), {"post_id": post_id})


def mark_error(post_id: str, error: str) -> None:
    now = int(time.time())
    with sync_session() as session:
        session.execute(text("DELETE FROM opinion_claims WHERE post_id = :post_id"), {"post_id": post_id})
        session.execute(text("""
            INSERT INTO opinion_claims (post_id, direction, status, error, created_at, updated_at)
            VALUES (:post_id, '未定向', 'error', :error, :now, :now)
        """), {"post_id": post_id, "error": error[:2000], "now": now})
        session.execute(text("DELETE FROM bigv_review_snapshots WHERE post_id = :post_id"), {"post_id": post_id})


def get_claims(post_ids: list[str]) -> dict[str, list[dict]]:
    if not post_ids:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(post_ids)))
    with sync_session() as session:
        rows = session.execute(text(f"""
            SELECT id, post_id, code, name, direction, claim, evidence, confidence, status, error, ignored
            FROM opinion_claims
            WHERE post_id IN ({placeholders})
            ORDER BY id
        """), {f"p{i}": value for i, value in enumerate(post_ids)}).mappings().all()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row["post_id"], []).append(dict(row))
    return result


def update_claim(
    claim_id: int,
    code: str | None = None,
    name: str | None = None,
    ignored: bool | None = None,
) -> bool:
    values = {"id": claim_id}
    assignments = []
    if code is not None:
        assignments.append("code = :code")
        values["code"] = code.strip() or None
    if name is not None:
        assignments.append("name = :name")
        values["name"] = name.strip() or None
    if ignored is not None:
        assignments.append("ignored = :ignored")
        values["ignored"] = ignored
    if not assignments:
        return False
    assignments.append("updated_at = :updated_at")
    values["updated_at"] = int(time.time())
    with sync_session() as session:
        result = session.execute(text(
            f"UPDATE opinion_claims SET {', '.join(assignments)} WHERE id = :id"
        ), values)
        if result.rowcount > 0:
            session.execute(text("""
                DELETE FROM bigv_review_snapshots
                WHERE post_id = (SELECT post_id FROM opinion_claims WHERE id = :id)
            """), {"id": claim_id})
    return result.rowcount > 0


def get_review_snapshots(post_ids: list[str]) -> dict[str, dict]:
    if not post_ids:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(post_ids)))
    with sync_session() as session:
        rows = session.execute(text(
            f"SELECT post_id, payload, finalized FROM bigv_review_snapshots WHERE post_id IN ({placeholders})"
        ), {f"p{i}": value for i, value in enumerate(post_ids)}).mappings().all()
    result = {}
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            result[str(row["post_id"])] = {"payload": payload, "finalized": bool(row["finalized"])}
    return result


def save_review_snapshot(post_id: str, payload: dict, finalized: bool) -> None:
    with sync_session() as session:
        session.execute(text(
            "INSERT INTO bigv_review_snapshots (post_id, payload, finalized, updated_at) "
            "VALUES (:post_id, :payload, :finalized, :updated_at) "
            "ON CONFLICT (post_id) DO UPDATE SET payload=EXCLUDED.payload, "
            "finalized=EXCLUDED.finalized, updated_at=EXCLUDED.updated_at"
        ), {"post_id": post_id, "payload": json.dumps(payload, ensure_ascii=False),
            "finalized": finalized, "updated_at": int(time.time())})


def delete_review_snapshot(post_id: str) -> None:
    with sync_session() as session:
        session.execute(text("DELETE FROM bigv_review_snapshots WHERE post_id = :post_id"), {"post_id": post_id})
