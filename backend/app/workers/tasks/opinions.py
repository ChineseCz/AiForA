"""LLM tasks for structured article opinion extraction."""
import asyncio
import csv
import io
from pathlib import Path

from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_DEFAULT, QUEUE_LLM


@celery_app.task(name="bigv_review.export", queue=QUEUE_DEFAULT)
def task_bigv_export(parameters: dict, source: str = "手动导出", job_id: int | None = None) -> None:
    from app.core.config import settings
    from app.core.db import async_session_maker
    from app.core.db import engine
    from app.repositories import jobs
    from app.services.bigv_review import WINDOWS, review_posts
    from app.workers.runner import job_run

    async def run():
        # Celery prefork workers may inherit asyncpg connections created by a
        # previous event loop. Replace the inherited pool before opening a
        # session on this task's loop.
        await engine.dispose(close=False)
        async with async_session_maker() as session:
            return await review_posts(session, user_id=str(parameters.get("user") or ""),
                                      start=str(parameters.get("start") or ""), end=str(parameters.get("end") or ""),
                                      limit=0, group_by_day=False)

    with job_run("bigv_export", source, job_id=job_id):
        result = asyncio.run(run())
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["日期", "大V", "AI标题", "原文标题", "方向", "标的", "代码", "验证状态",
                         *[f"{w}日收益" for w in WINDOWS], *[f"{w}日超额" for w in WINDOWS]])
        for item in result["items"]:
            targets = item.get("targets") or [{"name": "", "code": "", "performance": {}, "excess": {}}]
            for target in targets:
                writer.writerow([item.get("date"), item.get("user_name"), item.get("title"), item.get("source_title"),
                                 target.get("direction") or item.get("direction"), target.get("name"), target.get("code"),
                                 item.get("verdict"), *[target.get("performance", {}).get(str(w), "") for w in WINDOWS],
                                 *[target.get("excess", {}).get(str(w), "") for w in WINDOWS]])
        export_dir = Path(settings.data_dir).resolve() / "bigv_exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"bigv-review-{job_id or 'latest'}.csv"
        path.write_bytes(output.getvalue().encode("utf-8-sig"))
        if job_id is not None:
            jobs.set_artifact_path(job_id, str(path))
            jobs.update_progress(job_id, {"rows": sum(len(item.get("targets") or []) or 1 for item in result["items"]), "ready": 1})


@celery_app.task(name="bigv_review.run", queue=QUEUE_DEFAULT)
def task_bigv_review(
    user_id: str = "", start: str = "", end: str = "", limit: int = 0,
    group_by_day: bool = True, source: str = "手动", job_id: int | None = None,
    refresh_partial: bool = False,
) -> None:
    """Run the potentially large Big V review outside the API request."""
    from app.core.db import async_session_maker
    from app.core.db import engine
    from app.services.bigv_review import review_posts
    from app.workers.runner import job_run

    async def run() -> dict:
        await engine.dispose(close=False)
        async with async_session_maker() as session:
            return await review_posts(
                session, user_id=user_id, start=start, end=end,
                limit=limit, group_by_day=group_by_day, progress_callback=update_progress,
                cancel_callback=lambda: jobs.is_cancel_requested(job_id), refresh_partial=refresh_partial,
            )

    with job_run("bigv_review", source, invalidate_cache=False, job_id=job_id):
        print(f"开始复盘：{start or '最早文章'} 至 {end or '今天'}")
        from app.repositories import jobs

        def update_progress(progress: dict) -> None:
            if job_id is not None:
                jobs.update_progress(job_id, progress)

        result = asyncio.run(run())
        print(f"复盘完成：文章 {result.get('article_total', 0)} 篇，展示 {result.get('total', 0)} 条")


@celery_app.task(name="bigv_review.daily_tick", queue=QUEUE_DEFAULT)
def task_bigv_review_daily_tick() -> None:
    """Refresh recent unfinished snapshots after the market closes."""
    from datetime import date, timedelta
    from app.repositories import jobs
    if jobs.is_running("bigv_review"):
        return
    today = date.today()
    start = (today - timedelta(days=180)).isoformat()
    params = {"user": "", "start": start, "end": today.isoformat(), "limit": 0, "group_by_day": False}
    job_id = jobs.create_job("bigv_review", "定时增量复盘", params)
    task_bigv_review.delay(user_id="", start=start, end=today.isoformat(), limit=0,
                           group_by_day=False, source="定时增量复盘", job_id=job_id,
                           refresh_partial=True)


@celery_app.task(name="opinion.extract", queue=QUEUE_LLM)
def task_extract_opinions(post_id: str) -> None:
    from app.repositories import opinions
    from app.repositories import sync_data as db
    from app.services.opinion_extractor import extract

    post = db.get_post(post_id)
    if not post or not post.get("text"):
        return
    try:
        claims, raw = extract(post.get("title") or "", post.get("text") or "")
        opinions.replace_claims(post_id, claims, raw)
        from app.core.cache import bump_dataver_sync
        bump_dataver_sync()
        print(f"观点提取完成：{post_id}，{len(claims)} 条")
    except Exception as exc:  # noqa: BLE001
        opinions.mark_error(post_id, str(exc))
        print(f"观点提取失败：{post_id}，{exc}")
