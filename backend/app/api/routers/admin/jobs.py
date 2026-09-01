"""管理员：后台任务触发 + 状态。Phase 2 已接入 Celery + job_runs。

触发 = 若该类任务无在跑则 .delay() 入队；状态 = 读 job_runs 最新一条（形状兼容旧 *_state）。
注：Phase 3 将给整个 admin/ 加鉴权；当前公开只读模型下这些是"写/触发"操作，暂未鉴权。
"""
import json
import csv
import io

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.core.markdown import render_md
from app.repositories import jobs
from app.repositories import wechat_imports
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
    if kind == "wechat_import" and args and isinstance(args[0], list):
        await run_in_threadpool(wechat_imports.register_urls, args[0])
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
    return await jobs.get_job_status(session, "crawl")


@router.post("/index/sync")
async def index_sync(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_index_sync
    return await _trigger(session, "index_sync", task_index_sync, source="manual")


@router.get("/index/sync/status")
async def index_sync_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "index_sync")


@router.post("/wechat/import")
async def wechat_import(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.wechat import task_import_article
    body = await _json_body(request)
    raw_urls = body.get("urls") if isinstance(body.get("urls"), list) else [body.get("url")]
    urls = list(dict.fromkeys(str(url).strip() for url in raw_urls if str(url).strip()))
    if not urls:
        return JSONResponse({"error": "请输入微信公众号文章链接"}, status_code=400)
    if len(urls) > 200:
        return JSONResponse({"error": "单次最多导入 200 篇文章"}, status_code=400)
    return await _trigger(session, "wechat_import", task_import_article, urls, source="手动")


@router.get("/wechat/import/status")
async def wechat_import_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "wechat_import")


@router.get("/wechat/import/items")
async def wechat_import_items():
    return {
        "summary": await run_in_threadpool(wechat_imports.get_summary),
        "items": await run_in_threadpool(wechat_imports.get_items),
    }


@router.post("/wechat/import-csv")
async def wechat_import_csv(file: UploadFile = File(...), session: AsyncSession = Depends(db_session)):
    """Import the url column from the CSV exported by the article crawler."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        return JSONResponse({"error": "请上传 CSV 文件"}, status_code=400)
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
        rows = csv.DictReader(io.StringIO(text))
        fieldnames = {str(name).strip().lower() for name in (rows.fieldnames or []) if name}
        if "url" not in fieldnames:
            return JSONResponse({"error": "CSV 必须包含 url 列"}, status_code=400)
        urls = []
        for row in rows:
            value = next((v for k, v in row.items() if str(k).strip().lower() == "url"), "")
            value = (value or "").strip()
            if value and value.startswith(("http://", "https://")):
                urls.append(value)
    except (UnicodeDecodeError, csv.Error) as exc:
        return JSONResponse({"error": f"CSV 解析失败：{exc}"}, status_code=400)
    urls = list(dict.fromkeys(urls))
    if not urls:
        return JSONResponse({"error": "CSV 中没有有效文章链接"}, status_code=400)
    if len(urls) > 200:
        return JSONResponse({"error": "单次最多导入 200 篇文章"}, status_code=400)
    from app.workers.tasks.wechat import task_import_article
    return await _trigger(session, "wechat_import", task_import_article, urls, source="CSV 批量导入")


@router.post("/wechat/discover")
async def wechat_discover(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.wechat import task_discover
    body = await _json_body(request)
    keyword = str(body.get("keyword") or "主升龙神").strip()
    pages = max(1, min(3, int(body.get("pages", 1) or 1)))
    return await _trigger(session, "wechat_discover", task_discover, keyword, pages, source="手动")


@router.get("/wechat/discover/status")
async def wechat_discover_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "wechat_discover")


# ================= 总结生成 =================
@router.post("/summarize")
async def summarize(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.summarize import task_summarize
    body = await _json_body(request)
    ptype = body.get("type", "daily")
    if ptype not in PERIOD_TYPES:
        return {"started": False, "error": "未知的总结类型"}
    if await jobs.any_running(session, "summarize"):
        return {"started": False, "running": True, "error": "已有任务正在运行，请稍后再试"}
    job_id = await run_in_threadpool(jobs.create_job, "summarize", "手动")
    task_summarize.delay(
        ptype, str(body.get("start", "")), str(body.get("end", "")),
        str(body.get("user", "")), bool(body.get("regen", False)), "手动", job_id,
    )
    return {"started": True, "running": True}


@router.get("/summarize/status")
async def summarize_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "summarize")


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
    return await jobs.get_job_status(session, "stock_sync")


@router.get("/jobs/recent")
async def recent_jobs(session: AsyncSession = Depends(db_session)):
    """最近任务历史，供管理后台集中查看。"""
    return {"items": await jobs.list_recent_jobs(session)}


@router.get("/jobs/data-health")
async def data_health(session: AsyncSession = Depends(db_session)):
    """检查行情最新交易日、当天记录数和 K 线回补失败数。"""
    from sqlalchemy import text

    row = (await session.execute(text(
        """
        SELECT
          (SELECT MAX(trade_date) FROM stock_daily) AS stock_date,
          (SELECT COUNT(*) FROM stock_daily WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily)) AS stock_count,
          (SELECT MAX(trade_date) FROM bond_daily) AS bond_date,
          (SELECT COUNT(*) FROM bond_daily WHERE trade_date = (SELECT MAX(trade_date) FROM bond_daily)) AS bond_count,
          (SELECT COUNT(*) FROM backfill_failures) AS backfill_failures,
          (SELECT status FROM job_runs WHERE kind = 'stock_sync' ORDER BY id DESC LIMIT 1) AS stock_sync_status,
          (SELECT started_at FROM job_runs WHERE kind = 'stock_sync' ORDER BY id DESC LIMIT 1) AS stock_sync_started_at,
          (SELECT finished_at FROM job_runs WHERE kind = 'stock_sync' ORDER BY id DESC LIMIT 1) AS stock_sync_finished_at,
          (SELECT log FROM job_runs WHERE kind = 'stock_sync' ORDER BY id DESC LIMIT 1) AS stock_sync_log,
          (SELECT error FROM job_runs WHERE kind = 'stock_sync' ORDER BY id DESC LIMIT 1) AS stock_sync_error
        """
    ))).mappings().one()
    result = dict(row)
    log_lines = [line for line in (result.pop("stock_sync_log") or "").splitlines() if line.strip()]
    result["stock_sync_summary"] = log_lines[-1] if log_lines else ""
    if result["stock_sync_started_at"] and result["stock_sync_finished_at"]:
        result["stock_sync_duration_seconds"] = max(0, result["stock_sync_finished_at"] - result["stock_sync_started_at"])
    else:
        result["stock_sync_duration_seconds"] = None
    return result


@router.get("/jobs/backfill-failures")
async def backfill_failures(session: AsyncSession = Depends(db_session)):
    """当前历史 K 线回补失败标的，供后台查看和重试。"""
    from sqlalchemy import text

    rows = (await session.execute(text(
        """
        SELECT asset_type, code, last_job_id, error, updated_at
        FROM backfill_failures
        ORDER BY updated_at DESC, asset_type, code
        """
    ))).mappings().all()
    return {"items": [dict(row) for row in rows]}


@router.post("/stock/backfill")
async def stock_backfill(request: Request, session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.browser import task_backfill
    body = await _json_body(request)
    try:
        days = max(20, min(500, int(body.get("days", 60) or 60)))
    except (TypeError, ValueError):
        days = 60
    asset_type = body.get("asset_type", "all")
    if asset_type not in ("all", "stock", "bond"):
        asset_type = "all"
    failed_only = bool(body.get("failed_only", False))
    if await jobs.any_running(session, "stock_backfill"):
        return {"started": False, "running": True}
    job_id = await run_in_threadpool(jobs.create_job, "stock_backfill", "手动")
    task_backfill.delay(
        days=days,
        source="手动",
        job_id=job_id,
        asset_type=asset_type,
        failed_only=failed_only,
    )
    return {"started": True, "running": True}


@router.get("/stock/backfill/status")
async def stock_backfill_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "stock_backfill")


@router.post("/stock/finance_sync")
async def finance_sync(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_finance_sync
    return await _trigger(session, "finance_sync", task_finance_sync, source="手动")


@router.get("/stock/finance_sync/status")
async def finance_sync_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "finance_sync")


@router.post("/bond/sync")
async def bond_sync(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_bond_sync
    return await _trigger(session, "bond_sync", task_bond_sync, source="手动")


@router.get("/bond/sync/status")
async def bond_sync_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "bond_sync")


@router.post("/bond/basic_sync")
async def bond_basic_sync(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_bond_basic_sync
    return await _trigger(session, "bond_basic_sync", task_bond_basic_sync, source="手动")


@router.get("/bond/basic_sync/status")
async def bond_basic_sync_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "bond_basic_sync")


@router.post("/stock/sync-sectors")
async def sync_sectors(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_sector_catalog
    return await _trigger(session, "sector_sync", task_sector_catalog, source="手动")


@router.get("/stock/sync-sectors/status")
async def sync_sectors_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "sector_sync")


@router.post("/stock/sync-sector-members")
async def sync_sector_members(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.stock import task_sector_members
    return await _trigger(session, "sector_members_sync", task_sector_members, source="手动")


@router.get("/stock/sync-sector-members/status")
async def sync_sector_members_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "sector_members_sync")


@router.post("/stock/sync-xueqiu-sectors")
async def sync_xueqiu_sectors(session: AsyncSession = Depends(db_session)):
    from app.workers.tasks.browser import task_sync_xueqiu_sectors
    return await _trigger(session, "sync_xueqiu_sectors", task_sync_xueqiu_sectors, source="手动")


@router.get("/stock/sync-xueqiu-sectors/status")
async def sync_xueqiu_sectors_status(session: AsyncSession = Depends(db_session)):
    return await jobs.get_job_status(session, "sync_xueqiu_sectors")


# ================= 僵尸任务清理 =================
@router.post("/jobs/cleanup-zombie")
async def cleanup_zombie(session: AsyncSession = Depends(db_session)):
    """清理僵尸任务（超过 2 小时仍在 running 的任务）。"""
    import time
    from sqlalchemy import text

    now = int(time.time())
    timeout_seconds = 2 * 3600  # 2 小时

    result = await session.execute(text(
        """
        UPDATE job_runs
        SET status = 'error', finished_at = :now, error = '任务超时，手动清理'
        WHERE status = 'running' AND started_at < :threshold
        """
    ), {"now": now, "threshold": now - timeout_seconds})
    await session.commit()

    return {"cleaned": result.rowcount}
