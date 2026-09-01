"""微信公众号文章导入任务。"""
import random
import time

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_BROWSER
from app.workers.runner import job_run


def _wait_between_wechat_requests(index: int) -> None:
    if index <= 1:
        return
    low = max(0.0, min(settings.wechat_request_delay_min, settings.wechat_request_delay_max))
    high = max(low, settings.wechat_request_delay_max)
    time.sleep(random.uniform(low, high))


@celery_app.task(name="wechat.import_article", queue=QUEUE_BROWSER)
def task_import_article(urls: list[str] | str, source: str = "手动", job_id: int | None = None) -> None:
    from app.repositories import sync_data as db
    from app.scrapers.wechat import parse_article
    from app.workers.tasks.browser import task_summarize_daily_one, task_summarize_post_brief
    from app.workers.tasks.opinions import task_extract_opinions

    with job_run("wechat_import", source, invalidate_cache=True, job_id=job_id):
        if isinstance(urls, str):
            urls = [urls]
        unique_urls = list(dict.fromkeys(u.strip() for u in urls if u.strip()))
        print(f"开始导入微信公众号文章：{len(unique_urls)} 篇")
        summary_targets: set[tuple[str, str, str]] = set()
        for index, url in enumerate(unique_urls, 1):
            _wait_between_wechat_requests(index)
            try:
                article = parse_article(url)
                db.upsert_post(article)
                print(f"[{index}/{len(unique_urls)}] 已导入：{article['user_name']} - {article['title']}")
                task_summarize_post_brief.delay(article["id"])
                task_extract_opinions.delay(article["id"])
                summary_targets.add((article["user_id"], article["user_name"], article["date"]))
            except Exception as exc:  # noqa: BLE001
                print(f"[{index}/{len(unique_urls)}] 导入失败：{url}；{exc}")
        for user_id, user_name, date_str in summary_targets:
            task_summarize_daily_one.delay(user_id, user_name, date_str, regen=True)
        if summary_targets:
            print(f"已派发 {len(summary_targets)} 份微信文章日总结任务")


@celery_app.task(name="wechat.discover", queue=QUEUE_BROWSER)
def task_discover(keyword: str, pages: int = 1, source: str = "手动", job_id: int | None = None) -> None:
    from app.scrapers.wechat import parse_article
    from app.scrapers.wechat_discovery import discover
    from app.repositories import sync_data as db
    from app.workers.tasks.browser import task_summarize_daily_one, task_summarize_post_brief

    with job_run("wechat_discover", source, invalidate_cache=True, job_id=job_id):
        candidates = discover(keyword, pages)
        resolved = [item["url"] for item in candidates if item["url"]]
        print(f"搜索到 {len(candidates)} 篇候选，成功解析真实链接 {len(resolved)} 篇")
        if not resolved:
            print("搜狗跳转触发 antispider；可将候选文章在微信中打开后复制链接导入")
            return
        summary_targets: set[tuple[str, str, str]] = set()
        for index, url in enumerate(resolved, 1):
            _wait_between_wechat_requests(index)
            try:
                article = parse_article(url)
                db.upsert_post(article)
                task_summarize_post_brief.delay(article["id"])
                summary_targets.add((article["user_id"], article["user_name"], article["date"]))
                print(f"[{index}/{len(resolved)}] 已导入：{article['title']}")
            except Exception as exc:  # noqa: BLE001
                print(f"[{index}/{len(resolved)}] 导入失败：{url}；{exc}")
        for user_id, user_name, date_str in summary_targets:
            task_summarize_daily_one.delay(user_id, user_name, date_str, regen=True)
        if summary_targets:
            print(f"已派发 {len(summary_targets)} 份微信文章日总结任务")
