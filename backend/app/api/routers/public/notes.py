"""复盘笔记接口。"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_visitor
from app.core.db import async_session_maker
from app.repositories import notes as notes_repo
from app.repositories import trades as trades_repo

router = APIRouter(prefix="/api")

_SSE_HEADERS = {"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
_CONCURRENCY = 3  # 同时跑几个 LLM 请求
_DISCONNECT_POLL_SEC = 2.0  # 客户端中止后，最长这么久检测到并停止后续 LLM 调用


async def _gen_stream(dates: list[str], user_id: str, request: Request):
    """并发调 LLM，按完成顺序流式 yield SSE 行。DB 读写保持串行。

    注意：不复用路由注入的 session —— 路由函数一返回 StreamingResponse，
    FastAPI 就会关闭其依赖的 session，而生成器此时还没开始跑，
    写库会全部作用在已关闭的 session 上悄悄丢失。这里自己开一个
    存活到生成器结束的 session。
    """
    if not dates:
        yield f"data: {json.dumps({'done': True, 'generated': 0, 'dates': []})}\n\n"
        return

    from app.services.review_gen import generate_daily_review

    async with async_session_maker() as session:
        # 1. 串行预取所有当日交易（共用 session，不能并发）
        positions = await trades_repo.get_positions(session, user_id)
        all_trades: dict[str, list] = {}
        for d in dates:
            all_trades[d] = await trades_repo.list_trades_by_date(session, user_id, d)

        total = len(dates)
        sem = asyncio.Semaphore(_CONCURRENCY)
        queue: asyncio.Queue = asyncio.Queue()

        # 2. 并发启动所有 LLM 任务
        async def llm_one(d: str):
            async with sem:
                try:
                    content = await run_in_threadpool(generate_daily_review, d, all_trades[d], positions)
                except Exception:
                    content = f"# {d} 复盘\n\nAI 生成失败，请手动填写。\n"
                await queue.put((d, content))

        tasks = [asyncio.create_task(llm_one(d)) for d in dates]
        # 单个持久的 get 任务：wait() 超时只是"这轮没结果"，不能像 wait_for 那样每轮重新
        # 创建 queue.get() ——否则旧的 get() 还挂在 queue 上，下一轮又起一个新的去抢，
        # 谁先抢到谁的结果就没人接收，笔记悄悄丢失且不再 yield。
        get_task: asyncio.Task = asyncio.ensure_future(queue.get())

        # 3. 按完成顺序取结果，串行写库，逐条 yield 进度；客户端中止时取消剩余任务
        try:
            completed = 0
            generated: list[str] = []
            while completed < total:
                done, _ = await asyncio.wait({get_task}, timeout=_DISCONNECT_POLL_SEC)
                if not done:
                    if await request.is_disconnected():
                        return
                    continue
                d, content = get_task.result()
                get_task = asyncio.ensure_future(queue.get())
                await notes_repo.upsert_note(session, user_id, d, content)
                completed += 1
                generated.append(d)
                yield f"data: {json.dumps({'progress': completed, 'total': total, 'date': d})}\n\n"

            yield f"data: {json.dumps({'done': True, 'generated': len(generated), 'dates': generated})}\n\n"
        finally:
            if not get_task.done():
                get_task.cancel()
            for t in tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(get_task, *tasks, return_exceptions=True)


@router.get("/notes")
async def api_get_notes(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    favorite_only: bool = False,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    if date:
        note = await notes_repo.get_note(session, user_id, date)
        return {"note": note, "error": ""}
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    items, total = await notes_repo.list_notes(
        session, user_id, start_date, end_date, page, page_size, favorite_only
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size, "error": ""}


@router.patch("/notes/{note_date}/favorite")
async def api_toggle_note_favorite(
    note_date: str,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    note = await notes_repo.toggle_favorite(session, user_id, note_date)
    if not note:
        raise HTTPException(404, "note not found")
    return {"note": note, "error": ""}


class UpsertNoteBody(BaseModel):
    date: str
    content: str


@router.post("/notes")
async def api_upsert_note(
    body: UpsertNoteBody,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    note = await notes_repo.upsert_note(session, user_id, body.date, body.content)
    return {"note": note, "error": ""}


class GenerateNoteBody(BaseModel):
    date: str


@router.post("/notes/generate")
async def api_generate_note(
    body: GenerateNoteBody,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    from app.core.config import settings
    if not settings.relay_api_key:
        raise HTTPException(503, "未配置 LLM API key")
    trades = await trades_repo.list_trades_by_date(session, user_id, body.date)
    positions = await trades_repo.get_positions(session, user_id)
    from app.services.review_gen import generate_daily_review
    content = await run_in_threadpool(generate_daily_review, body.date, trades, positions)
    return {"content": content, "error": ""}


@router.delete("/notes")
async def api_delete_note(
    date: str,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    ok = await notes_repo.delete_note(session, user_id, date)
    if not ok:
        raise HTTPException(404, "note not found")
    return {"error": ""}


class BatchGenerateBody(BaseModel):
    start_date: str
    end_date: str


@router.post("/notes/batch-generate")
async def api_batch_generate_notes(
    body: BatchGenerateBody,
    request: Request,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    from app.core.config import settings
    if not settings.relay_api_key:
        raise HTTPException(503, "未配置 LLM API key")
    dates = await notes_repo.list_dates_with_trades_in_range(
        session, user_id, body.start_date, body.end_date
    )
    return StreamingResponse(_gen_stream(dates, user_id, request), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/notes/regen-all")
async def api_regen_all_notes(
    request: Request,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    from app.core.config import settings
    if not settings.relay_api_key:
        raise HTTPException(503, "未配置 LLM API key")
    dates = await notes_repo.list_all_note_dates(session, user_id)
    return StreamingResponse(_gen_stream(dates, user_id, request), media_type="text/event-stream", headers=_SSE_HEADERS)
