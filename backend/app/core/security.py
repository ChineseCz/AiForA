"""管理员鉴权原语（Phase 3）：bcrypt 密码哈希 + JWT 签发/校验。"""
import time

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    typ: str = "admin",
    expire_minutes: int | None = None,
    sty: str | None = None,
) -> str:
    """签发 JWT。

    sty（sub type）供访客 token 记录登录方式，避免 /me 串行三次 DB 查询：
    'phone' | 'wechat' | 'email'，管理员 token 不传。
    """
    now = int(time.time())
    minutes = expire_minutes if expire_minutes is not None else settings.jwt_expire_minutes
    payload: dict = {
        "sub": subject,
        "typ": typ,
        "iat": now,
        "exp": now + minutes * 60,
    }
    if sty is not None:
        payload["sty"] = sty
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """校验并解码 JWT；无效/过期返回 None。"""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
