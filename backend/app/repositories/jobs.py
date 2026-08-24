"""任务执行记录的增删改查。"""
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


def create_job(kind: str, source: str = "手动") -> int:
    """创建一条新的任务记录，返回 job_id。"""
    now = int(time.time())
    with sync_session() as s:
        row = s.execute(text(
            "INSERT INTO job_runs (kind, status, source, log, error, started_at, finished_at) "
            "VALUES (:kind, 'running', :source, '', '', :now, NULL) RETURNING id"
        ), {"kind": kind, "source": source, "now": now}).first()
        return row[0]


def append_log(job_id: int, message: str):
    """追加日志到任务记录。"""
    with sync_session() as s:
        s.execute(text(
            "UPDATE job_runs SET log = log || :msg WHERE id = :id"
        ), {"id": job_id, "msg": message + "\n"})


def finish_job(job_id: int, error: str = ""):
    """标记任务完成或失败。"""
    now = int(time.time())
    status = "error" if error else "success"
    with sync_session() as s:
        s.execute(text(
            "UPDATE job_runs SET status = :status, finished_at = :now, error = :err WHERE id = :id"
        ), {"id": job_id, "status": status, "now": now, "err": error})


async def get_job_status(session: AsyncSession, kind: str) -> dict:
    """获取某类任务的最新状态（用于轮询）。"""
    row = (await session.execute(text(
        "SELECT status, started_at, finished_at, log, error FROM job_runs "
        "WHERE kind = :k ORDER BY id DESC LIMIT 1"
    ), {"k": kind})).mappings().first()
    if not row:
        return {"running": False}

    result = {
        "running": row["status"] == "running",
        "error": row["error"] or "",
        "log": [line for line in (row["log"] or "").split("\n") if line.strip()],
    }
    if row["finished_at"]:
        from datetime import datetime, timezone, timedelta
        tz_cst = timezone(timedelta(hours=8))
        result["finished_at"] = datetime.fromtimestamp(row["finished_at"], tz=tz_cst).strftime("%Y-%m-%d %H:%M")
    return result
