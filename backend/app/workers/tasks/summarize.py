"""AI 总结任务（QUEUE_LLM）：从旧 web.py _run_summarize 移植区间生成逻辑。"""
from app.workers.celery_app import celery_app
from app.workers.queues import QUEUE_DEFAULT, QUEUE_LLM
from app.workers.runner import job_run


def _name_of(user_id: str) -> str:
    from app.repositories import sync_data as db
    for uid, name in db.get_distinct_users():
        if uid == user_id:
            return name
    return user_id


@celery_app.task(name="summarize.run", queue=QUEUE_LLM)
def task_summarize(ptype: str, start_str: str = "", end_str: str = "",
                   user_id: str = "", regen: bool = False, source: str = "手动",
                   job_id: int | None = None) -> None:
    from datetime import date, datetime

    from app.repositories import sync_data as db
    from app.services import summaries_build

    # invalidate_cache=True：否则 /api/summary 的 Redis 缓存 key（内嵌 dataver）不会失效，
    # regen 已经把新内容写进 DB，读接口却继续命中旧缓存直到 TTL 自然过期，页面上看不出任何变化。
    with job_run("summarize", source, invalidate_cache=True, job_id=job_id):
        today = date.today()
        start = datetime.strptime(start_str, "%Y-%m-%d").date() if start_str else today
        end = datetime.strptime(end_str, "%Y-%m-%d").date() if end_str else start
        if end < start:
            start, end = end, start

        targets = [(user_id, _name_of(user_id))] if user_id else db.get_distinct_users()
        if not targets:
            print("⚠️ 库里还没有帖子，先采集。")
            return

        for uid, uname in targets:
            if ptype == "highlights":
                summaries_build.gen_highlights_range(uid, uname, start, end)
                continue
            builder, keyfn = summaries_build.BUILDERS[ptype]
            anchors = summaries_build.period_anchors(ptype, start, end)
            print(f"→ {uname} · {ptype} 共 {len(anchors)} 个周期")
            done = 0
            for a in anchors:
                content = builder(uid, uname, a, regen)
                if content:
                    done += 1
                    print(f"  ✅ {keyfn(a)}")
            print(f"  {uname}：生成 {done} 份")
        print("🎉 总结完成")


@celery_app.task(name="summarize.weekly_tick", queue=QUEUE_DEFAULT)
def task_weekly_summary_tick() -> None:
    """周三/周日 20:00 的门槛任务（见 celery_app.py 的 beat_schedule crontab）。

    summarize.run 本身也被管理后台"生成 AI 总结"手动触发复用，不能直接在它里面加开关判断
    （会连手动触发也一起挡住）；开关判断放在这个专门的定时门槛任务里，仿照
    tasks/beat.py::scheduler_tick 读 schedules 表的模式，满足才派发 summarize.run。
    """
    from app.repositories import sync_data as db

    if not db.get_schedule().get("weekly_summary_enabled", True):
        return
    task_summarize.delay(ptype="weekly", source="定时(周总结)")
