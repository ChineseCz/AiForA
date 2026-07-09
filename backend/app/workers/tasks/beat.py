"""定时调度：Celery beat 每分钟触发一次 tick，读 schedules 表决定是否派发采集。

取代旧 web.py 的 _scheduler_loop（内置 20s 轮询线程）。逻辑等价：在 [start, end] 窗口内、
每 interval 分钟触发一次；同一时间槽只触发一次（用 Redis 记录已触发槽位去重）。
"""
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_DEFAULT


def _parse_hhmm(s: str, default: tuple[int, int]) -> tuple[int, int]:
    try:
        h, m = s.split(":")
        return int(h), int(m)
    except Exception:
        return default


@celery_app.task(name="beat.tick", queue=QUEUE_DEFAULT)
def scheduler_tick() -> None:
    from datetime import datetime

    from app.repositories import sync_data as db

    cfg = db.get_schedule()
    if not cfg.get("enabled"):
        return

    now = datetime.now()
    sh, sm = _parse_hhmm(cfg["start"], (8, 0))
    eh, em = _parse_hhmm(cfg["end"], (22, 0))
    interval = max(5, int(cfg["interval"]))
    start_dt = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end_dt = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    if end_dt <= start_dt:
        end_dt = now.replace(hour=23, minute=59, second=0, microsecond=0)
    if not (start_dt <= now <= end_dt):
        return

    slot = int((now - start_dt).total_seconds() // 60 // interval)
    # 用 Redis SETNX 去重：同一天同一槽位只触发一次（TTL 1 天）
    import redis as sync_redis

    from app.core.config import settings
    dedup_key = f"natapp:beat:{now.date().isoformat()}:{slot}"
    rc = sync_redis.from_url(settings.redis_url, decode_responses=True)
    try:
        if rc.set(dedup_key, "1", nx=True, ex=86400):
            from app.workers.tasks.browser import task_crawl
            task_crawl.delay(source="定时", summarize=True)
    finally:
        rc.close()
