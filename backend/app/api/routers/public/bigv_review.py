from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.services.bigv_review import review_posts

router = APIRouter(prefix="/api/bigv-review")


@router.get("")
async def public_bigv_review(
    user: str = Query(""), start: str = Query(""), end: str = Query(""),
    limit: int = Query(200, ge=1, le=200), group_by_day: bool = Query(True), session: AsyncSession = Depends(db_session),
):
    return await review_posts(session, user_id=user, start=start, end=end, limit=limit, group_by_day=group_by_day)
