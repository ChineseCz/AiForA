"""AI summary tasks."""
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_DEFAULT, QUEUE_LLM
from app.workers.runner import job_run

def _name_of(user_id: str) -> str:
    from app.repositories import sync_data as db
    for uid, name in db.get_distinct_users():
        if uid == user_id:
            return name
    return user_id

@celery_app.task(name="summarize.run", queue=QUEUE_LLM)
def task_summarize(ptype: str, start_str: str = "", end_str: str = "", user_id: str = "", regen: bool = False, source: str = "手动", job_id: int | None = None) -> None:
    from datetime import date, datetime
    from app.repositories import jobs
    from app.repositories import sync_data as db
    from app.services import summaries_build
    with job_run("summarize", source, invalidate_cache=True, job_id=job_id):
        today = date.today()
        start = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        end = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else start
        if end < start:
            start, end = end, start
        targets = [(user_id, _name_of(user_id))] if user_id else db.get_distinct_users()
        if not targets:
            print("数据库里还没有帖子，先采集。")
            return
        work = []
        for uid, uname in targets:
            if ptype == "highlights":
                work.append((uid, uname, None))
            else:
                work.extend((uid, uname, anchor) for anchor in summaries_build.period_anchors(ptype, start, end))
        total = len(work)
        completed = success = skipped = failed = 0
        if job_id is not None:
            jobs.update_progress(job_id, {"total": total, "completed": 0, "current": 0, "success": 0, "skipped": 0, "failed": 0, "current_user": "", "current_period": ""})
        for uid, uname, anchor in work:
            label = f"{start} ~ {end}" if anchor is None else str(anchor)
            try:
                if anchor is None:
                    has_posts = bool(db.get_top_posts(uid, start.isoformat(), end.isoformat(), 1))
                    summaries_build.gen_highlights_range(uid, uname, start, end)
                    success += 1 if has_posts else 0
                    skipped += 0 if has_posts else 1
                else:
                    builder, keyfn = summaries_build.BUILDERS[ptype]
                    content = builder(uid, uname, anchor, regen)
                    label = keyfn(anchor)
                    if content:
                        success += 1
                        print(f"✅ {uname} · {label}")
                    else:
                        skipped += 1
                        print(f"⏭️ {uname} · {label}：无帖子，跳过")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"❌ {uname} · {label}：{exc}")
            completed += 1
            if job_id is not None:
                jobs.update_progress(job_id, {"total": total, "completed": completed, "current": completed, "success": success, "skipped": skipped, "failed": failed, "current_user": "" if completed >= total else uname, "current_period": label})
        print(f"🎉 总结完成：成功 {success}，无帖子跳过 {skipped}，失败 {failed}")

@celery_app.task(name="summarize.weekly_tick", queue=QUEUE_DEFAULT)
def task_weekly_summary_tick() -> None:
    from app.repositories import sync_data as db
    if not db.get_schedule().get("weekly_summary_enabled", True):
        return
    task_summarize.delay(ptype="weekly", source="定时(周总结)")
