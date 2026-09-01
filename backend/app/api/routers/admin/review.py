import re

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import db_session
from app.core.cache import bump_dataver_sync

from app.repositories import opinions

router = APIRouter(prefix="/api/bigv-review")


@router.post("/extract")
async def extract_opinions(request: Request, session: AsyncSession = Depends(db_session)):
    from app.repositories import posts as posts_repo
    from app.workers.tasks.opinions import task_extract_opinions

    try:
        body = await request.json()
    except ValueError:
        body = {}
    post_ids = body.get("post_ids") if isinstance(body, dict) else []
    if not isinstance(post_ids, list) or not post_ids:
        rows = await posts_repo.get_posts(session, limit=200, offset=0)
        post_ids = [row["id"] for row in rows["items"]]
    post_ids = list(dict.fromkeys(str(post_id) for post_id in post_ids if post_id))[:200]
    for post_id in post_ids:
        opinions.mark_pending(post_id)
        task_extract_opinions.delay(post_id)
    bump_dataver_sync()
    return {"started": True, "count": len(post_ids)}


@router.patch("/claim/{claim_id}")
async def update_opinion_claim(claim_id: int, request: Request):
    body = await request.json()
    code = body.get("code") if isinstance(body, dict) else None
    name = body.get("name") if isinstance(body, dict) else None
    ignored = body.get("ignored") if isinstance(body, dict) else None
    if code is not None and (not isinstance(code, str) or (code and not re.fullmatch(r"\d{6}", code.strip()))):
        return {"updated": False, "error": "股票代码必须是 6 位数字"}
    if ignored is not None and not isinstance(ignored, bool):
        return {"updated": False, "error": "ignored 必须是布尔值"}
    updated = opinions.update_claim(claim_id, code=code, name=name, ignored=ignored)
    if updated:
        bump_dataver_sync()
    return {"updated": updated}
