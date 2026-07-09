"""浏览器依赖任务（QUEUE_BROWSER，Windows 宿主 worker 专用）：雪球抓取 + K线回补。

延迟导入 scrapers.*（内部又延迟导入 playwright），使本模块可在容器 worker 里被 Celery 注册而不报错；
真正执行仅在宿主 worker 上发生。
"""
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_BROWSER
from app.workers.runner import job_run


@celery_app.task(name="browser.crawl", queue=QUEUE_BROWSER)
def task_crawl(source: str = "手动", summarize: bool = True, job_id: int | None = None) -> None:
    from datetime import date

    from app.scrapers import xueqiu
    with job_run("crawl", source, invalidate_cache=True, job_id=job_id):
        xueqiu.crawl_all()
        if summarize:
            # 采集后生成当日日总结（复用 LLM 队列任务，异步派发，不阻塞抓取任务收尾）
            from app.repositories import sync_data as db
            today = date.today().isoformat()
            print("… 派发今日总结任务 …")
            for uid, uname in db.get_distinct_users():
                task_summarize_daily_one.delay(uid, uname, today)
            print("✅ 今日总结任务已派发")


@celery_app.task(name="browser.backfill", queue=QUEUE_BROWSER)
def task_backfill(days: int = 60, delay: float = 0.5, source: str = "手动", job_id: int | None = None) -> None:
    from app.scrapers import kline
    with job_run("stock_backfill", source, invalidate_cache=True, job_id=job_id):
        kline.backfill_history(days, delay)
    # 历史K线变化 → 触发预计算指标重算（default 队列，由容器 worker 消费）
    from app.workers.tasks.stock import task_recompute_indicators
    task_recompute_indicators.delay(source="自动(回补后)")


# 在此声明以便 crawl 派发；真正实现见 tasks/summarize.py，避免循环导入用延迟引用
@celery_app.task(name="summarize.daily_one", queue="llm")
def task_summarize_daily_one(user_id: str, user_name: str, date_str: str) -> None:
    from datetime import datetime

    from app.services import summaries_build
    from app.workers.runner import job_run as _jr
    with _jr("summarize", "自动(采集后)"):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        content = summaries_build.ensure_daily(user_id, user_name, d)
        print(f"  {user_name} {date_str}: {'✅' if content else '无帖子跳过'}")
