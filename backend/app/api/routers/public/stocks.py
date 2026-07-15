"""个股详情：K线 / 基本面 / 相关新闻。计算/外部抓取均跑 threadpool。"""
from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.services import views
from app.services.external import sina

router = APIRouter(prefix="/api")


@router.get("/stock/quote")
async def api_stock_quote(code: str = Query(default=""), c: CacheService = Depends(cache)):
    """个股实时行情（秒级轮询专用）：不走 dataver 版本失效，用 1s 短TTL 兜底防打爆上游。"""
    code = code.strip()
    if not code:
        return JSONResponse({"error": "缺少股票代码"}, status_code=400)
    key = f"natapp:quote:{code}"
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    quote = await run_in_threadpool(sina.fetch_realtime_quote, code)
    result = quote or {"error": "暂无行情"}
    await c.set_json(key, result, settings.cache_ttl_quote)
    return result


@router.get("/stock/kline")
async def api_stock_kline(code: str = Query(default=""), c: CacheService = Depends(cache)):
    code = code.strip()
    if not code:
        return JSONResponse(
            {"error": "缺少股票代码", "code": "", "name": "", "bars": []}, status_code=400
        )
    key = await c.key("kline", code=code)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    view = await run_in_threadpool(views.get_kline_view, code)
    view["error"] = ""
    await c.set_json(key, view, settings.cache_ttl_kline)
    return view


@router.get("/index/kline")
async def api_index_kline(code: str = Query(default="sh000001"), c: CacheService = Depends(cache)):
    """大盘指数日线（看板首页），不落库，直连新浪，60s TTL 保证盘中实时刷新。"""
    code = code.strip() or "sh000001"
    key = await c.key("index_kline", code=code)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    view = await run_in_threadpool(views.get_index_kline_view, code)
    view["error"] = ""
    await c.set_json(key, view, 60)
    return view


@router.get("/stock/fundamentals")
async def api_stock_fundamentals(
    code: str = Query(default=""), days: int = Query(default=90), c: CacheService = Depends(cache)
):
    code = code.strip()
    if not code:
        return JSONResponse({"error": "缺少股票代码"}, status_code=400)
    days = max(1, min(365, days))
    key = await c.key("fundamentals", code=code, days=days)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    view = await run_in_threadpool(views.get_fundamentals_view, code, days)
    view["error"] = ""
    await c.set_json(key, view, settings.cache_ttl_fundamentals)
    return view


@router.get("/stock/news")
async def api_stock_news(
    code: str = Query(default=""), days: int = Query(default=14), c: CacheService = Depends(cache)
):
    code = code.strip()
    if not code:
        return JSONResponse({"error": "缺少股票代码", "items": []}, status_code=400)
    days = max(1, min(60, days))
    key = await c.key("news", code=code, days=days)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    items = await run_in_threadpool(sina.fetch_stock_news, code, days)
    result = {"items": items, "days": days, "error": ""}
    await c.set_json(key, result, settings.cache_ttl_news)
    return result


@router.get("/stock/search")
async def api_stock_search(
    q: str = Query(default="", max_length=20),
    limit: int = Query(default=10, le=20),
    session: AsyncSession = Depends(db_session),
):
    """按名称或代码模糊搜索股票，返回最新交易日的 {code, name} 列表。"""
    q = q.strip()
    if not q:
        return {"items": []}
    pattern = f"%{q}%"
    rows = (await session.execute(
        text(
            """
            SELECT code, name FROM stock_daily
            WHERE trade_date = (SELECT MAX(trade_date) FROM stock_daily)
              AND (name ILIKE :p OR code LIKE :p)
            ORDER BY
              CASE WHEN code = :exact THEN 0 WHEN name ILIKE :exact THEN 1 ELSE 2 END,
              name
            LIMIT :lim
            """
        ),
        {"p": pattern, "exact": q, "lim": limit},
    )).mappings().all()
    return {"items": [{"code": r["code"], "name": r["name"]} for r in rows]}
