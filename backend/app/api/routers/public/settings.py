"""用户级设置读写接口（选股参数持久化等）。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session, require_visitor
from app.repositories import settings as settings_repo

router = APIRouter(prefix="/api")

_ALLOWED_KEYS = {"screen_params"}


@router.get("/user/settings")
async def get_user_settings(
    key: str,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    if key not in _ALLOWED_KEYS:
        raise HTTPException(400, f"不支持的 key: {key}")
    raw = await settings_repo.get_user_setting(session, user_id, key)
    value = json.loads(raw) if raw else None
    return {"key": key, "value": value, "error": ""}


class SaveSettingBody(BaseModel):
    key: str
    value: object


@router.put("/user/settings")
async def save_user_settings(
    body: SaveSettingBody,
    user_id: str = Depends(require_visitor),
    session: AsyncSession = Depends(db_session),
):
    if body.key not in _ALLOWED_KEYS:
        raise HTTPException(400, f"不支持的 key: {body.key}")
    await settings_repo.upsert_user_setting(session, user_id, body.key, json.dumps(body.value, ensure_ascii=False))
    return {"error": ""}


@router.get("/settings/defaults")
async def get_system_defaults(
    key: str,
    session: AsyncSession = Depends(db_session),
):
    """公开只读：读取系统全局默认设置（如管理员设置的全局选股参数默认值）。"""
    if key not in _ALLOWED_KEYS:
        raise HTTPException(400, f"不支持的 key: {key}")
    raw = await settings_repo.get_system_setting(session, key)
    value = json.loads(raw) if raw else None
    return {"key": key, "value": value, "error": ""}
