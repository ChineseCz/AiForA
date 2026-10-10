from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_DEFAULT
import asyncio


@celery_app.task(name="strategy_review.capture_daily", queue=QUEUE_DEFAULT)
def task_capture_daily(job_id: int | None = None) -> dict:
    from app.services.strategy_review import capture_daily
    from app.workers.runner import job_run
    with job_run("strategy_review", "每日收盘自动复盘", job_id=job_id):
        return capture_daily()


@celery_app.task(name="strategy_review.daily_tick", queue=QUEUE_DEFAULT)
def task_strategy_review_daily_tick() -> None:
    from datetime import datetime
    from app.repositories import jobs
    if datetime.now().weekday() < 5 and not jobs.is_running("strategy_review"):
        task_capture_daily.delay()


@celery_app.task(name="strategy_review.combination", queue=QUEUE_DEFAULT)
def task_strategy_combination(params: dict, job_id: int | None = None) -> None:
    from app.core.db import async_session_maker
    from app.repositories import jobs
    from app.services.strategy_review import run_expression_combination
    from app.workers.runner import job_run

    run_params = dict(params)
    for key in ("buy_strategies", "sell_strategies"):
        if isinstance(run_params.get(key), str):
            run_params[key] = [x for x in run_params[key].split(",") if x]

    async def run() -> dict:
        async with async_session_maker() as session:
            def report(processed: int, total: int) -> None:
                pct = round(processed / total * 100, 1) if total else 0
                jobs.update_progress(job_id, {
                    "phase": "running",
                    "message": f"正在计算信号：{processed}/{total} 只股票（{pct}%）",
                    "processed_codes": processed,
                    "total_codes": total,
                    "percent": pct,
                })
            return await run_expression_combination(session, progress_callback=report, **run_params)

    with job_run("strategy_combination", "组合策略回测", job_id=job_id):
        jobs.update_progress(job_id, {"phase": "running", "message": "正在扫描历史行情并计算信号"})
        result = asyncio.run(run())
        jobs.update_parameters(job_id, {"result": result})
        jobs.update_progress(job_id, {"phase": "done", "message": "组合回测完成", "summary": result.get("summary", {})})
