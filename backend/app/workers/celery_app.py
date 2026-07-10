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
        # 全市场行情：固定每10分钟一次（不经 schedules 表配置，任务内部按交易时段自行判断是否跳过）
        "stock-auto-sync": {"task": "stock.auto_sync_tick", "schedule": 600.0},
        # 周总结：每周三、周日 20:00（day_of_week: 0=周日）生成全部大V本周周总结。
        # 直接复用手动触发用的 summarize.run 任务（不新建任务函数），user_id 留空 = 全部大V，
        # start/end 留空 = 以当天为锚点（period_anchors 会算出本周周一）。
        "weekly-summary": {
            "task": "summarize.run",
            "schedule": crontab(hour=20, minute=0, day_of_week="0,3"),
            "kwargs": {"ptype": "weekly", "source": "定时(周总结)"},
        },
    },
)

# 注册任务：import 使 @celery_app.task 装饰器执行。task 内部对 playwright/openai 均为延迟导入，
# 因此容器 worker（无 playwright）import 这些模块不会报错，只有执行浏览器任务才需要。
from app.workers.tasks import beat, browser, stock, summarize  # noqa: E402,F401
