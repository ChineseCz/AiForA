"""帖子流分页查询。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cache, db_session
from app.core.cache import CacheService
from app.core.config import settings
from app.repositories import posts as posts_repo

router = APIRouter(prefix="/api")


@router.get("/posts")
async def api_posts(
    user: str | None = Query(default=None),
    start: str = Query(default=""),
    end: str = Query(default=""),
    q: str = Query(default=""),
    page: int = Query(default=1),
    size: int = Query(default=30),
    session: AsyncSession = Depends(db_session),
    c: CacheService = Depends(cache),
):
    page = max(1, page)
    size = min(100, max(5, size))
    user_id = user or None
    key = await c.key("posts", user=user_id, start=start, end=end, q=q, page=page, size=size)
    hit = await c.get_json(key)
    if hit is not None:
        return hit
    data = await posts_repo.get_posts(session, user_id, start, end, q, limit=size, offset=(page - 1) * size)
    data["page"] = page
    data["size"] = size
    await c.set_json(key, data, settings.cache_ttl_posts)
    return data
