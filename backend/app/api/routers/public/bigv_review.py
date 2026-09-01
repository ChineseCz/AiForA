from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.services.bigv_review import review_posts

router = APIRouter(prefix="/api/bigv-review")


@router.get("")
async def public_bigv_review(
    user: str = Query(""), start: str = Query(""), end: str = Query(""),
    limit: int = Query(0, ge=0), group_by_day: bool = Query(True), session: AsyncSession = Depends(db_session), c: CacheService = Depends(cache),
):
    key = await c.key("bigv_review", user=user, start=start, end=end, limit=limit, group_by_day=group_by_day)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    result = await review_posts(session, user_id=user, start=start, end=end, limit=limit, group_by_day=group_by_day)
    await c.set_json(key, result, settings.cache_ttl_bigv_review)
    return result
