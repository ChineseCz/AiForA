"""任务执行记录的增删改查。"""
import json
import time
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sync_db import sync_session


async def any_running(session: AsyncSession, kind: str) -> bool:
    """检查是否有正在运行的任务，自动清理超时僵尸任务（超过 2 小时未完成视为异常）。"""
    now = int(time.time())
    timeout_seconds = 2 * 3600  # 2 小时

    # 先清理僵尸任务：started_at 距今超过 2 小时且仍然 running
    await session.execute(text(
        """
        UPDATE job_runs
        SET status = 'error', finished_at = :now, error = '任务超时，自动标记失败'
        WHERE kind = :k AND status = 'running' AND started_at < :threshold
        """
    ), {"k": kind, "now": now, "threshold": now - timeout_seconds})
    await session.commit()

    # 再检查是否还有 running 任务
    return (await session.execute(text(
        "SELECT 1 FROM job_runs WHERE kind = :k AND status = 'running' LIMIT 1"
    ), {"k": kind})).first() is not None


def is_running(kind: str) -> bool:
    """同步任务使用的运行状态检查，供 Celery beat/worker 调用。"""
    with sync_session() as s:
        row = s.execute(text(
            "SELECT 1 FROM job_runs WHERE kind = :k AND status = 'running' LIMIT 1"
        ), {"k": kind}).first()
        return row is not None


def is_job_finished(job_id: int) -> bool:
    """按任务 ID 检查任务是否已经结束，防止成功任务重复投递。"""
    with sync_session() as s:
        row = s.execute(text(
            "SELECT status FROM job_runs WHERE id = :id LIMIT 1"
        ), {"id": job_id}).first()
        return row is not None and row[0] in ("done", "success")


def create_job(kind: str, source: str = "手动", parameters: dict | None = None) -> int:
    """创建一条新的任务记录，返回 job_id。"""
    now = int(time.time())
    with sync_session() as s:
        row = s.execute(text(
            "INSERT INTO job_runs (kind, status, source, log, error, started_at, finished_at, parameters) "
            "VALUES (:kind, 'running', :source, '', '', :now, NULL, CAST(:parameters AS json)) RETURNING id"
        ), {"kind": kind, "source": source, "now": now, "parameters": json.dumps(parameters or {}, ensure_ascii=False)}).first()
        return row[0]


def append_log(job_id: int, message: str):
    """追加日志到任务记录。"""
    with sync_session() as s:
        s.execute(text(
            "UPDATE job_runs SET log = log || :msg WHERE id = :id"
        ), {"id": job_id, "msg": message + "\n"})


def update_progress(job_id: int, progress: dict) -> None:
    with sync_session() as s:
        s.execute(text(
            "UPDATE job_runs SET progress = CAST(:progress AS json) WHERE id = :id"
        ), {"id": job_id, "progress": json.dumps(progress, ensure_ascii=False)})


def set_artifact_path(job_id: int, path: str) -> None:
    with sync_session() as s:
        s.execute(text("UPDATE job_runs SET artifact_path = :path WHERE id = :id"), {"id": job_id, "path": path})


def request_cancel(job_id: int) -> bool:
    with sync_session() as s:
        result = s.execute(text(
            "UPDATE job_runs SET status = 'cancel_requested' WHERE id = :id AND status = 'running'"
        ), {"id": job_id})
        return result.rowcount > 0


def is_cancel_requested(job_id: int | None) -> bool:
    if job_id is None:
        return False
    with sync_session() as s:
        return s.execute(text(
            "SELECT 1 FROM job_runs WHERE id = :id AND status = 'cancel_requested'"
        ), {"id": job_id}).first() is not None


def finish_job(job_id: int, error: str = ""):
    """标记任务完成或失败。"""
    now = int(time.time())
    status = "error" if error else "success"
    if not error and get_status_sync(job_id) == "cancel_requested":
        status = "canceled"
    with sync_session() as s:
        s.execute(text(
            "UPDATE job_runs SET status = :status, finished_at = :now, error = :err WHERE id = :id"
        ), {"id": job_id, "status": status, "now": now, "err": error})


def get_status_sync(job_id: int) -> str | None:
    """Read a job status from synchronous Celery task code."""
    with sync_session() as s:
        return s.execute(text("SELECT status FROM job_runs WHERE id = :id"), {"id": job_id}).scalar()


async def get_job_status(session: AsyncSession, kind: str) -> dict:
    """获取某类任务的最新状态（用于轮询）。"""
    row = (await session.execute(text(
        "SELECT id, status, started_at, finished_at, log, error, progress, parameters, artifact_path FROM job_runs "
        "WHERE kind = :k ORDER BY id DESC LIMIT 1"
    ), {"k": kind})).mappings().first()
    if not row:
        return {"running": False}

    result = {
        "running": row["status"] in ("running", "cancel_requested"),
        "status": row["status"],
        "error": row["error"] or "",
        "log": [line for line in (row["log"] or "").split("\n") if line.strip()],
        "progress": row["progress"] or {},
        "job_id": row["id"],
        "parameters": row["parameters"] or {},
        "artifact_path": row["artifact_path"],
    }
    if row["finished_at"]:
        from datetime import datetime, timezone, timedelta
        tz_cst = timezone(timedelta(hours=8))
        result["finished_at"] = datetime.fromtimestamp(row["finished_at"], tz=tz_cst).strftime("%Y-%m-%d %H:%M")
    return result


async def list_recent_jobs(session: AsyncSession, limit: int = 20) -> list[dict]:
    """Return a compact cross-queue history for the admin dashboard."""
    limit = max(1, min(limit, 100))
    rows = (await session.execute(text(
        """
        SELECT id, kind, status, source, started_at, finished_at, error, RIGHT(COALESCE(log, ''), 12000) AS log
        FROM job_runs
        ORDER BY id DESC
        LIMIT :limit
        """
    ), {"limit": limit})).mappings().all()
    result = []
    for row in rows:
        item = dict(row)
        if item["started_at"] and item["finished_at"]:
            item["duration_seconds"] = max(0, item["finished_at"] - item["started_at"])
        else:
            item["duration_seconds"] = None
        result.append(item)
    return result
