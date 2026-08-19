"""job_runs 读写：取代旧的进程内 crawl_state/*_sync_state 内存字典 + /status 轮询。

写：Celery 任务（同步）创建/追加日志/收尾。读：状态接口（异步）取某类任务的最新一条。
"""
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sync_db import sync_session

LOG_CAP = 300  # 与旧 _TeeWriter 一致，最多保留最近 300 行


# ===== 同步写（任务用）=====
def create_job(kind: str, source: str = "手动") -> int:
    now = int(time.time())
    with sync_session() as s:
        row = s.execute(text(
            """
            INSERT INTO job_runs (kind, status, source, log, error, started_at, finished_at)
            VALUES (:kind, 'running', :source, '', '', :now, NULL)
            RETURNING id
            """
        ), {"kind": kind, "source": source, "now": now}).first()
        return row[0]


def append_log(job_id: int, lines: list[str]) -> None:
    """把新日志行拼到 log 末尾，保留最近 LOG_CAP 行。"""
    if not lines:
        return
    with sync_session() as s:
        cur = s.execute(text("SELECT log FROM job_runs WHERE id = :id"), {"id": job_id}).scalar() or ""
        existing = cur.split("\n") if cur else []
        merged = existing + lines
        if len(merged) > LOG_CAP:
            merged = merged[-LOG_CAP:]
        s.execute(text("UPDATE job_runs SET log = :log WHERE id = :id"),
                  {"log": "\n".join(merged), "id": job_id})


def finish_job(job_id: int, error: str = "") -> None:
    with sync_session() as s:
        s.execute(text(
            "UPDATE job_runs SET status = :st, error = :err, finished_at = :now WHERE id = :id"
        ), {"st": "error" if error else "done", "err": error, "now": int(time.time()), "id": job_id})


def is_running(kind: str) -> bool:
    with sync_session() as s:
        return s.execute(text(
            "SELECT 1 FROM job_runs WHERE kind = :k AND status = 'running' LIMIT 1"
        ), {"k": kind}).first() is not None


# ===== 异步读（状态接口用）=====
def _to_state(row) -> dict:
    """job_runs 行 → 旧 *_state 字典形状，前端无感知切换。"""
    if row is None:
        return {"running": False, "log": [], "error": "", "started_at": "", "finished_at": ""}

    def fmt(ts):
        if not ts:
            return ""
        from datetime import datetime, timezone, timedelta
        tz_cst = timezone(timedelta(hours=8))
        return datetime.fromtimestamp(ts, tz=tz_cst).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "running": row["status"] == "running",
        "log": (row["log"] or "").split("\n") if row["log"] else [],
        "error": row["error"] or "",
        "source": row["source"] or "",
        "started_at": fmt(row["started_at"]),
        "finished_at": fmt(row["finished_at"]),
    }


async def get_latest_state(session: AsyncSession, kind: str) -> dict:
    row = (await session.execute(text(
        "SELECT * FROM job_runs WHERE kind = :k ORDER BY id DESC LIMIT 1"
    ), {"k": kind})).mappings().first()
    return _to_state(row)


async def any_running(session: AsyncSession, kind: str) -> bool:
    return (await session.execute(text(
        "SELECT 1 FROM job_runs WHERE kind = :k AND status = 'running' LIMIT 1"
    ), {"k": kind})).first() is not None
