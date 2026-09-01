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
    n = 0
    with job_run("stock_sync", source, invalidate_cache=True, job_id=job_id) as current_job_id:
        n = ingest.sync_daily_snapshot()
    # job_run 会记录并吞掉异常；只有快照任务确实成功时才触发全表指标重算。
    from app.repositories import jobs
    if jobs.get_status_sync(current_job_id) == "success":
        task_recompute_indicators.delay(source="自动(快照后)")  # 快照更新 → 重算预计算指标
    return n


@celery_app.task(name="stock.index_sync", queue=QUEUE_DEFAULT)
def task_index_sync(source: str = "manual", job_id: int | None = None) -> int:
    from app.services import ingest
    with job_run("index_sync", source, invalidate_cache=False, job_id=job_id):
        return ingest.sync_index_benchmarks()


# A股交易时段（含集合竞价），只在工作日的这两段时间内派发定时同步；不做节假日日历——
# 节假日照样会派发但新浪快照数据没变化，多算一次预计算不影响正确性，只是浪费一点计算量。
_TRADING_WINDOWS = [((9, 15), (11, 30)), ((13, 0), (15, 5))]


def _in_trading_hours(now) -> bool:
    if now.weekday() >= 5:
        return False
    hm = (now.hour, now.minute)
    return any(start <= hm <= end for start, end in _TRADING_WINDOWS)


@celery_app.task(name="stock.auto_sync_tick", queue=QUEUE_DEFAULT)
def task_auto_sync_tick() -> None:
    """全市场行情定时同步（每分钟检查，按后台配置的分钟间隔派发）。

    beat_schedule 的周期是进程启动时固定的静态配置，没法运行时开关；开关做在任务体内部，
    仿照 tasks/beat.py::scheduler_tick 读 schedules 表的模式——不满足就直接 return。
    只在交易时段内派发；若上一轮 stock_sync 或其触发的 recompute_indicators（全表重算）
    还没跑完就跳过本轮——避免行情接口偶发变慢时任务在队列里越堆越多。
    """
    from datetime import datetime

    from app.repositories import jobs, sync_data as db

    if not db.get_schedule().get("stock_auto_sync_enabled", True):
        return
    now = datetime.now()
    interval = max(5, int(db.get_schedule().get("stock_sync_interval", 15) or 15))
    if not _in_trading_hours(now):
        return
    if jobs.is_running("stock_sync") or jobs.is_running("recompute_indicators"):
        print("… 上一轮行情同步/指标重算尚未结束，本轮跳过 …")
        return
    # 以 09:15 为交易日槽位起点；Redis SETNX 防止多个 beat 重复派发同一槽位。
    import redis as sync_redis
    from app.core.config import settings
    trading_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
    slot = int((now - trading_start).total_seconds() // 60 // interval)
    dedup_key = f"natapp:stock-sync:{now.date().isoformat()}:{slot}"
    rc = sync_redis.from_url(settings.redis_url, decode_responses=True)
    try:
        if rc.set(dedup_key, "1", nx=True, ex=86400):
            task_stock_sync.delay(source=f"定时({interval}分钟)")
    finally:
            rc.close()


@celery_app.task(name="stock.signal_notifications", queue=QUEUE_DEFAULT)
def task_signal_notifications() -> int:
    from app.services.notifications import scan_signal_notifications
    return scan_signal_notifications()


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


@celery_app.task(name="stock.bond_sync", queue=QUEUE_DEFAULT)
def task_bond_sync(source: str = "手动", job_id: int | None = None) -> int:
    from app.services import ingest
    with job_run("bond_sync", source, invalidate_cache=True, job_id=job_id):
        return ingest.sync_bond_snapshot()


@celery_app.task(name="stock.bond_basic_sync", queue=QUEUE_DEFAULT)
def task_bond_basic_sync(source: str = "手动", job_id: int | None = None) -> int:
    from app.services import ingest
    with job_run("bond_basic_sync", source, invalidate_cache=True, job_id=job_id):
        return ingest.sync_bond_basic()


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
