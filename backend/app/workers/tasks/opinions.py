"""LLM tasks for structured article opinion extraction."""
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_LLM


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
