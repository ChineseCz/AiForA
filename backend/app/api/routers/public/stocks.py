"""个股详情：K线 / 基本面 / 相关新闻。计算/外部抓取均跑 threadpool。"""
import json as _json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.core.markdown import render_md
from app.repositories import sync_data as db
from app.services import stock_ai, views
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
async def api_stock_kline(
    code: str = Query(default=""),
    sp: str = Query(default=""),
    c: CacheService = Depends(cache),
):
    code = code.strip()
    if not code:
        return JSONResponse(
            {"error": "缺少股票代码", "code": "", "name": "", "bars": []}, status_code=400
        )
    signal_params: dict | None = None
    if sp:
        try:
            parsed = _json.loads(sp)
            if isinstance(parsed, dict):
                signal_params = parsed
        except (ValueError, _json.JSONDecodeError):
            pass

    if not signal_params:
        key = await c.key("kline", code=code)
        hit = await c.get_json(key)
        if hit is not None:
            return hit
        view = await run_in_threadpool(views.get_kline_view, code, None)
        view["error"] = ""
        await c.set_json(key, view, settings.cache_ttl_kline)
        return view

    view = await run_in_threadpool(views.get_kline_view, code, signal_params)
    view["error"] = ""
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
    await c.set_json(key, view, 10)
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


async def _ai_analysis_key(code: str) -> str:
    trade_date = await run_in_threadpool(db.get_latest_trade_date) or "unknown"
    return f"natapp:ai_analysis:{trade_date}:{code}"


@router.get("/stock/ai-analysis")
async def api_get_stock_ai_analysis(code: str = Query(default=""), c: CacheService = Depends(cache)):
    """读取已生成的AI综合分析（不调用LLM）；没生成过返回 generated:false。"""
    code = code.strip()
    if not code:
        return JSONResponse({"error": "缺少股票代码"}, status_code=400)
    key = await _ai_analysis_key(code)
    hit = await c.get_json(key)
    if hit is not None:
        return {**hit, "generated": True, "error": ""}
    return {"content": "", "html": "", "generated": False, "error": ""}


@router.post("/stock/ai-analysis/generate")
async def api_generate_stock_ai_analysis(code: str = Query(default=""), c: CacheService = Depends(cache)):
    """实际调用LLM生成分析并写入缓存；同一交易日内命中缓存的用户共享结果，不重复调用LLM。"""
    code = code.strip()
    if not code:
        return JSONResponse({"error": "缺少股票代码"}, status_code=400)
    if not settings.relay_api_key:
        return JSONResponse({"error": "未配置 LLM API key"}, status_code=503)

    key = await _ai_analysis_key(code)
    result = await run_in_threadpool(stock_ai.generate_stock_analysis, code)
    if result.get("error"):
        return JSONResponse(result, status_code=400)
    result["html"] = render_md(result["content"])
    await c.set_json(key, result, settings.cache_ttl_ai_analysis)
    return {**result, "generated": True}


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


@router.get("/stock/etf/list")
async def api_etf_list(c: CacheService = Depends(cache)):
    """返回最新交易日的 ETF 列表。公开匿名只读，无需登录。

    A 股 ETF 的代码并不只有 51/15 开头：上交所还包含 50/56/58，
    深交所和跨市场基金还会使用 16 等前缀。这里沿用新浪 ETF 节点的
    快照数据落库方式，用完整的 ETF 代码段筛选，避免漏掉如 562500。
    """
    dataver = await c.version()
    key = f"etf:list:{dataver}"
    cached = await c.get_json(key)
    if cached:
        return {"etfs": cached, "cached": True}

    def _fetch():
        latest = db.get_latest_rows()
        etfs = [
            r for r in latest
            if r["code"].startswith(("15", "16", "50", "51", "56", "58"))
        ]
        return etfs

    etfs = await run_in_threadpool(_fetch)
    await c.set_json(key, etfs, settings.cache_ttl_kline)
    return {"etfs": etfs, "cached": False}


@router.get("/bond/list")
async def api_bond_list(
    q: str = Query(default="", max_length=20),
    limit: int = Query(default=500, le=2000),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    min_premium: float | None = Query(default=None),
    max_premium: float | None = Query(default=None),
    min_conversion: float | None = Query(default=None, ge=0),
    min_amount: float | None = Query(default=None, ge=0),
    rating: str = Query(default=""),
    risk: str = Query(default=""),
    c: CacheService = Depends(cache),
):
    """返回最新可转债行情；转股条款字段在后续资料同步中补齐。"""
    dataver = await c.version()
    key = f"bond:list:{dataver}:{q}:{limit}:{min_price}:{max_price}:{min_premium}:{max_premium}:{min_conversion}:{min_amount}:{rating}:{risk}"
    cached = await c.get_json(key)
    if cached is not None:
        return {"bonds": cached, "cached": True}
    def _filter():
        rows = db.get_latest_bond_rows(5000, q.strip())
        near_date = (date.today() + timedelta(days=180)).isoformat()
        result = []
        for row in rows:
            price, premium, conversion, amount = row.get("close"), row.get("premium_rate"), row.get("conversion_value"), row.get("amount")
            if min_price is not None and (price is None or price < min_price): continue
            if max_price is not None and (price is None or price > max_price): continue
            if min_premium is not None and (premium is None or premium < min_premium): continue
            if max_premium is not None and (premium is None or premium > max_premium): continue
            if min_conversion is not None and (conversion is None or conversion < min_conversion): continue
            if min_amount is not None and (amount is None or amount < min_amount): continue
            if rating and row.get("rating") != rating: continue
            tags = []
            if row.get("redeem_status"): tags.append("redeem")
            if row.get("maturity_date") and row["maturity_date"] <= near_date: tags.append("near_maturity")
            if premium is not None and premium >= 30: tags.append("high_premium")
            if risk and risk not in tags: continue
            row["risk_tags"] = tags
            result.append(row)
        return result[:limit]
    bonds = await run_in_threadpool(_filter)
    await c.set_json(key, bonds, settings.cache_ttl_kline)
    return {"bonds": bonds, "cached": False}


@router.get("/bond/backtest")
async def api_bond_backtest(
    start: str = Query(default=""), end: str = Query(default=""),
    max_premium: float = Query(default=10), max_price: float = Query(default=130),
    min_conversion: float = Query(default=100), hold_days: int = Query(default=5, ge=1, le=60),
):
    rows = await run_in_threadpool(db.get_bond_history_rows, start, end)
    dates = sorted({r["trade_date"] for r in rows})
    if len(dates) < hold_days + 1:
        return JSONResponse({"error": f"历史数据不足，至少需要 {hold_days + 1} 个交易日，当前只有 {len(dates)} 个"}, status_code=400)
    by_date = {d: [r for r in rows if r["trade_date"] == d] for d in dates}
    trades = []
    for i, d in enumerate(dates[:-hold_days]):
        future_date = dates[i + hold_days]
        selected = [r for r in by_date[d] if r.get("close") is not None and r.get("close") <= max_price
                    and r.get("premium_rate") is not None and r["premium_rate"] <= max_premium
                    and r.get("conversion_value") is not None and r["conversion_value"] >= min_conversion]
        future = {r["code"]: r for r in by_date[future_date]}
        returns = [(future[r["code"]]["close"] / r["close"] - 1) for r in selected if r["code"] in future and future[r["code"]].get("close")]
        if returns:
            trades.append({"date": d, "future_date": future_date, "count": len(returns), "return_pct": sum(returns) / len(returns) * 100})
    if not trades:
        return JSONResponse({"error": "没有符合条件的历史交易样本"}, status_code=400)
    returns = [t["return_pct"] for t in trades]
    return {"params": {"max_premium": max_premium, "max_price": max_price, "min_conversion": min_conversion, "hold_days": hold_days},
            "trades": trades, "trade_count": len(trades), "avg_return_pct": sum(returns) / len(returns),
            "win_rate_pct": sum(1 for x in returns if x > 0) / len(returns) * 100, "best_return_pct": max(returns), "worst_return_pct": min(returns)}


@router.get("/bond/detail")
async def api_bond_detail(code: str = Query(default=""), c: CacheService = Depends(cache)):
    code = code.strip()
    if not code:
        return JSONResponse({"error": "缺少转债代码"}, status_code=400)
    key = f"bond:detail:{await c.version()}:{code}"
    cached = await c.get_json(key)
    if cached is not None:
        return {"bond": cached, "cached": True}
    bond = await run_in_threadpool(db.get_latest_bond_by_code, code)
    if not bond:
        return JSONResponse({"error": "暂无转债数据"}, status_code=404)
    await c.set_json(key, bond, settings.cache_ttl_kline)
    return {"bond": bond, "cached": False}
