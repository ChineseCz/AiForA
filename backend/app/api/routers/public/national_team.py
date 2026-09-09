from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session
from app.services import national_team

router = APIRouter(prefix="/api")


@router.get("/national-team")
async def api_national_team(
    report_date: str | None = Query(None),
    institution: str | None = Query(None),
    change_type: str | None = Query(None),
    session: AsyncSession = Depends(db_session),
):
    return await national_team.get_national_team_holdings(session, report_date, institution, change_type)
