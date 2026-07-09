"""行情/财务/板块同步任务（QUEUE_DEFAULT，容器化 worker）。

数据同步类任务成功后失效读缓存（invalidate_cache=True）。job_id 由触发接口预建并传入，
使"running"状态入队即可见。
"""
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_DEFAULT
from app.workers.runner import job_run


@celery_app.task(name="stock.sync_snapshot", queue=QUEUE_DEFAULT)
def task_stock_sync(source: str = "手动", job_id: int | None = None) -> int:
    from app.services import ingest
    with job_run("stock_sync", source, invalidate_cache=True, job_id=job_id):
        n = ingest.sync_daily_snapshot()
    task_recompute_indicators.delay(source="自动(快照后)")  # 快照更新 → 重算预计算指标
    return n


@celery_app.task(name="stock.recompute_indicators", queue=QUEUE_DEFAULT)
def task_recompute_indicators(source: str = "手动", job_id: int | None = None) -> int:
    from app.services import indicator_precompute
    with job_run("recompute_indicators", source, invalidate_cache=True, job_id=job_id):
        return indicator_precompute.recompute_all()


@celery_app.task(name="stock.finance_sync", queue=QUEUE_DEFAULT)
def task_finance_sync(source: str = "手动", job_id: int | None = None) -> int:
    from app.services import ingest
    with job_run("finance_sync", source, invalidate_cache=True, job_id=job_id):
        return ingest.sync_finance_snapshot()


@celery_app.task(name="stock.sector_catalog", queue=QUEUE_DEFAULT)
def task_sector_catalog(source: str = "手动", job_id: int | None = None) -> int:
    from app.services import ingest
    with job_run("sector_sync", source, invalidate_cache=True, job_id=job_id):
        return ingest.sync_sector_catalog()


@celery_app.task(name="stock.sector_members", queue=QUEUE_DEFAULT)
def task_sector_members(source: str = "手动", job_id: int | None = None) -> int:
    from app.services import ingest
    with job_run("sector_members_sync", source, invalidate_cache=True, job_id=job_id):
        return ingest.sync_all_sector_members()
