"""Celery 应用定义（Phase 1 仅定义，不启动 worker）。Phase 2 注册任务并起 worker/beat。

浏览器队列 worker 在 Windows 宿主运行：
    celery -A app.workers.celery_app worker -Q browser --pool=solo
容器化 worker：
    celery -A app.workers.celery_app worker -Q default,llm --concurrency=4
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.workers.queues import QUEUE_DEFAULT

celery_app = Celery(
    "natapp",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_default_queue=QUEUE_DEFAULT,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    # beat：每分钟一次 tick，读 schedules 表决定是否派发采集（取代旧内置 20s 轮询线程）
    beat_schedule={
        "scheduler-tick": {"task": "beat.tick", "schedule": 60.0},
        # 全市场行情：固定每10分钟一次，任务内部读 schedules.stock_auto_sync_enabled 决定是否跳过。
        "stock-auto-sync": {"task": "stock.auto_sync_tick", "schedule": 600.0},
        # 周总结：每周三、周日 20:00（day_of_week: 0=周日）门槛检查，通过后派发 summarize.run
        # 生成全部大V本周周总结。指向门槛任务 summarize.weekly_tick 而不是直接指向 summarize.run，
        # 因为后者也被管理后台"生成 AI 总结"手动触发复用，开关只能挡定时这一条路径。
        "weekly-summary": {
            "task": "summarize.weekly_tick",
            "schedule": crontab(hour=20, minute=0, day_of_week="0,3"),
        },
    },
)

# 注册任务：import 使 @celery_app.task 装饰器执行。task 内部对 playwright/openai 均为延迟导入，
# 因此容器 worker（无 playwright）import 这些模块不会报错，只有执行浏览器任务才需要。
from app.workers.tasks import beat, browser, stock, summarize  # noqa: E402,F401
