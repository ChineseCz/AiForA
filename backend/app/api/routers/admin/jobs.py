"""管理员：后台任务触发 + 状态。Phase 2 已接入 Celery + job_runs。

触发 = 若该类任务无在跑则 .delay() 入队；状态 = 读 job_runs 最新一条（形状兼容旧 *_state）。
注：Phase 3 将给整个 admin/ 加鉴权；当前公开只读模型下这些是"写/触发"操作，暂未鉴权。
"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.markdown import render_md
from app.repositories import jobs
from app.repositories import summaries as sum_repo

router = APIRouter(prefix="/api")

PERIOD_TYPES = ("daily", "weekly", "monthly", "yearly", "highlights")


async def _json_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


async def _trigger(session: AsyncSession, kind: str, task, *args, **kwargs) -> dict:
    """预建 running 状态的 job_runs 行再入队，使'running'入队即可见（消除轮询竞态）。"""
    if await jobs.any_running(session, kind):
        return {"started": False, "running": True}
    job_id = await run_in_threadpool(jobs.create_job, kind, kwargs.pop("source", "手动"))
    task.delay(*args, job_id=job_id, **kwargs)
    return {"started": True, "running": True}


# ================= 采集 =================
@router.post("/crawl")
async def crawl(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.browser import task_crawl
    body = await _json_body(request)
    summarize = bool(body.get("summarize", True))
    return await _trigger(session, "crawl", task_crawl, source="手动", summarize=summarize)


@router.get("/crawl/status")
async def crawl_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_latest_state(session, "crawl")


# ================= 总结生成 =================
@router.post("/summarize")
async def summarize(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.summarize import task_summarize
    body = await _json_body(request)
    ptype = body.get("type", "daily")
    if ptype not in PERIOD_TYPES:
        return {"started": False, "error": "未知的总结类型"}
    if await jobs.any_running(session, "summarize"):
        return {"started": False, "running": True}
    job_id = await run_in_threadpool(jobs.create_job, "summarize", "手动")
    task_summarize.delay(
        ptype, str(body.get("start", "")), str(body.get("end", "")),
        str(body.get("user", "")), bool(body.get("regen", False)), "手动", job_id,
    )
    return {"started": True, "running": True}


@router.get("/summarize/status")
async def summarize_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_latest_state(session, "summarize")


@router.post("/feibi/ask")
async def feibi_ask(request: Request):
    from app.services import summarizer
    body = await _json_body(request)
    question = str(body.get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "说点什么嘛"}, status_code=400)
    raw_history = body.get("history") or []
    # 只信任 role/content 两个字段，且只认 user/assistant——不把前端传来的东西直接转发给 LLM API。
    # 最多留最近 20 轮，够聊了，也别把 prompt 喂得没边。
    history = [
        {"role": h["role"], "content": str(h["content"])[:2000]}
        for h in raw_history if isinstance(h, dict) and h.get("role") in ("user", "assistant") and h.get("content")
    ][-20:]
    # 前端各页面自己拼的一小段"我在看什么"（比如"当前在选股页，已筛出 xx 只"），只是文本提示，
    # 不当结构化数据信任——截断长度防止有人把这个字段塞爆当 prompt 注入。
    page_context = str(body.get("page_context") or "").strip()[:1000]
    try:
        answer = await run_in_threadpool(summarizer.ask_feibi, history, question, page_context)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=500)
    return {"answer": answer}


@router.post("/summary/ask")
async def summary_ask(request: Request, session: AsyncSession = Depends(db_session)):
    from app.services import summarizer
    body = await _json_body(request)
    user_id = str(body.get("user") or "")
    ptype = body.get("type", "daily")
    key = str(body.get("key") or "")
    question = str(body.get("question") or "").strip()
    if not question:
        return JSONResponse({"error": "请输入问题"}, status_code=400)
    content = await sum_repo.get_summary(session, user_id, ptype, key)
    if content is None:
        return JSONResponse({"error": "请先选择一份已生成的总结"}, status_code=400)
    try:
        answer = await run_in_threadpool(summarizer.ask_about_summary, content, question)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=500)
    return {"answer": answer, "html": render_md(answer)}


# ================= 行情/财务/板块同步 =================
@router.post("/stock/sync")
async def stock_sync(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_stock_sync
    return await _trigger(session, "stock_sync", task_stock_sync, source="手动")


@router.get("/stock/sync/status")
async def stock_sync_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_latest_state(session, "stock_sync")


@router.post("/stock/backfill")
async def stock_backfill(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.browser import task_backfill
    body = await _json_body(request)
    try:
        days = max(20, min(120, int(body.get("days", 60) or 60)))
    except (TypeError, ValueError):
        days = 60
    if await jobs.any_running(session, "stock_backfill"):
        return {"started": False, "running": True}
    job_id = await run_in_threadpool(jobs.create_job, "stock_backfill", "手动")
    task_backfill.delay(days=days, source="手动", job_id=job_id)
    return {"started": True, "running": True}


@router.get("/stock/backfill/status")
async def stock_backfill_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_latest_state(session, "stock_backfill")


@router.post("/stock/finance_sync")
async def finance_sync(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_finance_sync
    return await _trigger(session, "finance_sync", task_finance_sync, source="手动")


@router.get("/stock/finance_sync/status")
async def finance_sync_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_latest_state(session, "finance_sync")


@router.post("/stock/sync-sectors")
async def sync_sectors(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_sector_catalog
    return await _trigger(session, "sector_sync", task_sector_catalog, source="手动")


@router.get("/stock/sync-sectors/status")
async def sync_sectors_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_latest_state(session, "sector_sync")


@router.post("/stock/sync-sector-members")
async def sync_sector_members(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_sector_members
    return await _trigger(session, "sector_members_sync", task_sector_members, source="手动")


@router.get("/stock/sync-sector-members/status")
async def sync_sector_members_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_latest_state(session, "sector_members_sync")
