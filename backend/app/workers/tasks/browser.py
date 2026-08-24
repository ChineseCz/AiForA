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
        updated, pending_brief_ids = xueqiu.crawl_all()
        if summarize and updated:
            # 只给"本次真的抓到新帖子"的大V重新生成当日总结，且强制 regen——否则当天已生成过一次
            # 总结的大V，即使后续抓到了新帖子，ensure_daily 命中缓存也不会重新生成，页面看不出变化。
            today = date.today().isoformat()
            print(f"… 派发今日总结任务（{len(updated)} 位大V有新帖）…")
            for uid, (uname, n) in updated.items():
                task_summarize_daily_one.delay(uid, uname, today, regen=True)
            print("✅ 今日总结任务已派发")
        if pending_brief_ids:
            print(f"… 派发帖子一句话总结任务（{len(pending_brief_ids)} 条长帖）…")
            for pid in pending_brief_ids:
                task_summarize_post_brief.delay(pid)
            print("✅ 一句话总结任务已派发")


@celery_app.task(name="browser.backfill", queue=QUEUE_BROWSER)
def task_backfill(days: int = 60, delay: float = 0.5, source: str = "手动", job_id: int | None = None, asset_type: str = "all") -> None:
    if job_id is not None:
        from app.repositories import jobs
        if jobs.is_job_finished(job_id):
            print(f"跳过重复的历史K线回补任务：job_id={job_id} 已成功完成")
            return
    from app.scrapers import kline
    with job_run("stock_backfill", source, invalidate_cache=True, job_id=job_id):
        kline.backfill_history(days, delay, asset_type=asset_type)
    # 历史K线变化 → 触发预计算指标重算（default 队列，由容器 worker 消费）
    from app.workers.tasks.stock import task_recompute_indicators
    task_recompute_indicators.delay(source="自动(回补后)")


@celery_app.task(name="browser.sync_xueqiu_sectors", queue=QUEUE_BROWSER)
def task_sync_xueqiu_sectors(source: str = "手动", job_id: int | None = None) -> None:
    """雪球板块（申万行业分类，含半导体/软件开发等新浪没有的细分行业）全量同步。

    需要登录态 + 真实浏览器（雪球板块接口拒绝匿名请求，成分股表格也是纯前端渲染），
    只能走宿主 browser 队列，不能像新浪板块那样容器化。耗时较长（134个行业逐个翻页）。
    """
    from app.repositories import sync_data as db
    from app.scrapers import xueqiu
    with job_run("sync_xueqiu_sectors", source, invalidate_cache=True, job_id=job_id):
        items = xueqiu.sync_xueqiu_sectors()
        n_sectors, n_codes = db.save_xueqiu_sectors(items)
        print(f"✅ 已落库 {n_sectors} 个雪球行业，共 {n_codes} 条成分股关系")


# 在此声明以便 crawl 派发；真正实现见 tasks/summarize.py，避免循环导入用延迟引用
@celery_app.task(name="summarize.daily_one", queue="llm")
def task_summarize_daily_one(user_id: str, user_name: str, date_str: str, regen: bool = False) -> None:
    from datetime import datetime

    from app.services import summaries_build
    from app.workers.runner import job_run as _jr
    with _jr("summarize", "自动(采集后)", invalidate_cache=True):
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        content = summaries_build.ensure_daily(user_id, user_name, d, regen=regen)
        print(f"  {user_name} {date_str}: {'✅' if content else '无帖子跳过'}")


@celery_app.task(name="summarize.post_brief", queue="llm")
def task_summarize_post_brief(post_id: str) -> None:
    """给帖子流里的单条长帖子生成一句话摘要（抓取后自动派发，见 task_crawl）。"""
    from app.core.cache import bump_dataver_sync
    from app.repositories import sync_data as db
    from app.services import summarizer

    post = db.get_post(post_id)
    if not post or not post.get("text"):
        return
    try:
        brief = summarizer.summarize_post_brief(post["text"], post.get("title") or "")
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  帖子 {post_id} 一句话总结失败：{e}")
        return
    if brief:
        db.save_post_brief(post_id, brief)
        bump_dataver_sync()
