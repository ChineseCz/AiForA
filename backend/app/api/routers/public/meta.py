"""元信息：用户列表、筛选字段、板块名录。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.repositories import posts as posts_repo
from app.repositories import sectors as sectors_repo
from app.services.matching import pinyin_abbr

router = APIRouter(prefix="/api")

# 与 web.py STOCK_FIELD_META 一致
STOCK_FIELD_META = [
    {"field": "change_pct", "label": "涨跌幅(%)"},
    {"field": "close", "label": "最新价"},
    {"field": "volume", "label": "成交量"},
    {"field": "amount", "label": "成交额"},
    {"field": "turnover_rate", "label": "换手率(%)"},
    {"field": "pe_ttm", "label": "市盈率(动态)"},
    {"field": "pb", "label": "市净率"},
    {"field": "total_mv", "label": "总市值(万元)"},
    {"field": "circ_mv", "label": "流通市值(万元)"},
]


@router.get("/users")
async def api_users(session: AsyncSession = Depends(db_session)):
    return await posts_repo.get_distinct_users(session)


@router.get("/screen/fields")
async def api_screen_fields():
    return STOCK_FIELD_META


@router.get("/screen/sectors")
async def api_screen_sectors(
    session: AsyncSession = Depends(db_session),
    c: CacheService = Depends(cache),
):
    key = await c.key("screen_sectors")
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    rows = await sectors_repo.get_sector_catalog(session)
    for r in rows:
        r["abbr"] = pinyin_abbr(r["name"])
    await c.set_json(key, rows, settings.cache_ttl_sectors)
    return rows
