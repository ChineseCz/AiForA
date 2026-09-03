import csv
import io
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.repositories import jobs
from app.services.bigv_review import _summary, review_posts

router = APIRouter(prefix="/api/bigv-review")


@router.post("/run")
async def start_bigv_review(request: Request, session: AsyncSession = Depends(db_session)):
    """Queue a historical review so the HTTP request is not held open."""
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    if await jobs.any_running(session, "bigv_review"):
        return {"started": False, "running": True}
    from app.workers.tasks.opinions import task_bigv_review

    parameters = {
        "user": str(body.get("user") or ""), "start": str(body.get("start") or ""),
        "end": str(body.get("end") or ""), "limit": max(0, int(body.get("limit") or 0)),
        "group_by_day": bool(body.get("group_by_day", True)),
    }
    job_id = await run_in_threadpool(jobs.create_job, "bigv_review", "手动", parameters)
    task_bigv_review.delay(
        user_id=parameters["user"], start=parameters["start"], end=parameters["end"],
        limit=parameters["limit"], group_by_day=parameters["group_by_day"],
        source="手动",
        job_id=job_id,
    )
    return {"started": True, "running": True, "job_id": job_id}


@router.post("/run/{job_id}/cancel")
async def cancel_bigv_review(job_id: int):
    canceled = await run_in_threadpool(jobs.request_cancel, job_id)
    return {"canceled": canceled, "job_id": job_id}


@router.post("/run/retry")
async def retry_bigv_review(session: AsyncSession = Depends(db_session)):
    if await jobs.any_running(session, "bigv_review"):
        return {"started": False, "running": True}
    latest = await session.execute(text(
        "SELECT parameters FROM job_runs WHERE kind = 'bigv_review' ORDER BY id DESC LIMIT 1"
    ))
    row = latest.mappings().first()
    params = row["parameters"] if row and row["parameters"] else {}
    from app.workers.tasks.opinions import task_bigv_review
    job_id = await run_in_threadpool(jobs.create_job, "bigv_review", "重试", params)
    task_bigv_review.delay(
        user_id=str(params.get("user") or ""), start=str(params.get("start") or ""),
        end=str(params.get("end") or ""), limit=max(0, int(params.get("limit") or 0)),
        group_by_day=bool(params.get("group_by_day", True)), source="重试", job_id=job_id,
    )
    return {"started": True, "running": True, "job_id": job_id}


@router.get("/run/status")
async def bigv_review_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "bigv_review")


@router.get("")
async def public_bigv_review(
    user: str = Query(""), start: str = Query(""), end: str = Query(""),
    limit: int = Query(0, ge=0), group_by_day: bool = Query(True), direction: str = Query(""),
    verdict: str = Query(""), extraction_status: str = Query(""), target_threshold: float = Query(3.0, ge=0, le=100), saved_only: bool = Query(False),
    session: AsyncSession = Depends(db_session), c: CacheService = Depends(cache),
):
    # v2 invalidates cached read-only results created before partial snapshots
    # were included in saved_only mode.
    key = await c.key("bigv_review_v2", user=user, start=start, end=end, limit=limit, group_by_day=group_by_day,
                      direction=direction, verdict=verdict, extraction_status=extraction_status, target_threshold=target_threshold, saved_only=saved_only)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    result = await review_posts(session, user_id=user, start=start, end=end, limit=limit,
                                group_by_day=group_by_day, target_threshold=target_threshold, saved_only=saved_only)
    if direction or verdict or extraction_status:
        result["items"] = [item for item in result["items"]
                           if (not direction or item.get("direction") == direction)
                           and (not verdict or item.get("verdict") == verdict)
                           and (not extraction_status or item.get("extraction_status") == extraction_status)]
        result["total"] = len(result["items"])
        result["summary"] = _summary(result["items"], target_threshold=target_threshold)
        result["summary"]["article_total"] = result["article_total"]
    await c.set_json(key, result, settings.cache_ttl_bigv_review)
    return result


@router.get("/export")
async def export_bigv_review(
    user: str = Query(""), start: str = Query(""), end: str = Query(""), direction: str = Query(""),
    verdict: str = Query(""), extraction_status: str = Query(""), target_threshold: float = Query(3.0, ge=0, le=100),
    session: AsyncSession = Depends(db_session),
):
    result = await review_posts(session, user_id=user, start=start, end=end, limit=0, group_by_day=False,
                                target_threshold=target_threshold)
    items = [item for item in result["items"]
             if (not direction or item.get("direction") == direction)
             and (not verdict or item.get("verdict") == verdict)
             and (not extraction_status or item.get("extraction_status") == extraction_status)]
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["日期", "大V", "AI标题", "原文标题", "方向", "标的", "代码", "验证状态",
                     "1日收益", "3日收益", "5日收益", "7日收益", "10日收益", "20日收益", "60日收益", "120日收益",
                     "1日超额", "3日超额", "5日超额", "7日超额", "10日超额", "20日超额", "60日超额", "120日超额"])
    for item in items:
        for target in item.get("targets") or [{"name": "", "code": "", "performance": {}, "excess": {}}]:
            writer.writerow([item.get("date"), item.get("user_name"), item.get("title"), item.get("source_title"),
                             target.get("direction") or item.get("direction"), target.get("name"), target.get("code"),
                             item.get("verdict"), *[target.get("performance", {}).get(str(w), "") for w in WINDOWS],
                             *[target.get("excess", {}).get(str(w), "") for w in WINDOWS]])
    content = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(io.BytesIO(content), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=bigv-review.csv"})


@router.post("/export/run")
async def start_bigv_export(request: Request, session: AsyncSession = Depends(db_session)):
    try:
        body = await request.json()
    except (ValueError, json.JSONDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    if await jobs.any_running(session, "bigv_export"):
        return {"started": False, "running": True}
    parameters = {"user": str(body.get("user") or ""), "start": str(body.get("start") or ""),
                  "end": str(body.get("end") or "")}
    from app.workers.tasks.opinions import task_bigv_export
    job_id = await run_in_threadpool(jobs.create_job, "bigv_export", "手动导出", parameters)
    task_bigv_export.delay(parameters, source="手动导出", job_id=job_id)
    return {"started": True, "running": True, "job_id": job_id}


@router.get("/export/status")
async def bigv_export_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "bigv_export")


@router.get("/export/download/{job_id}")
async def download_bigv_export(job_id: int, session: AsyncSession = Depends(db_session)):
    row = (await session.execute(text("SELECT artifact_path, status FROM job_runs WHERE id = :id AND kind = 'bigv_export'"), {"id": job_id})).mappings().first()
    if not row or row["status"] != "success" or not row["artifact_path"]:
        return {"ready": False, "error": "导出文件尚未生成"}
    from pathlib import Path
    path = Path(row["artifact_path"]).resolve()
    if not path.is_file():
        return {"ready": False, "error": "导出文件不存在"}
    return FileResponse(path, media_type="text/csv", filename=f"bigv-review-{job_id}.csv")
