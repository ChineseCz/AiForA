"""访客账号（手机号+验证码 / 微信扫码）登录（Phase 9）。此路由不加管理员守卫，登录本身要开放。"""
import json
import logging
import re
import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import _is_visitor_mode_enabled, cache, db_session, require_visitor, require_visitor_payload
from app.core.cache import CacheService
from app.core.config import settings
from app.core.ratelimit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories import users as users_repo
from app.services.external import wechat
from app.services.external.email import send_verification_email
from app.services.external.sms import send_sms

logger = logging.getLogger("app.user_auth")

router = APIRouter(prefix="/api/user")
auth_config_router = APIRouter(prefix="/api/auth")

_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WX_TOKEN_REDIS_KEY = "wx:access_token"
_WX_SCENE_PREFIX = "wx:scene:"
_WX_SCENE_EXPIRE = 300


def _code_key(phone: str) -> str:
    return f"smscode:{phone}"


def _resend_key(phone: str) -> str:
    return f"smscode:resend:{phone}"


def _email_code_key(email: str) -> str:
    return f"emailcode:{email}"


def _email_resend_key(email: str) -> str:
    return f"emailcode:resend:{email}"


async def _json_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


async def _wx_access_token(redis) -> str:
    cached = await redis.get(_WX_TOKEN_REDIS_KEY)
    if cached:
        return cached
    token = await run_in_threadpool(wechat.fetch_access_token, settings.wechat_appid, settings.wechat_appsecret)
    await redis.set(_WX_TOKEN_REDIS_KEY, token, ex=7000)
    return token


# ===== 手机号+验证码 =====

@router.post("/send-code")
@limiter.limit(settings.rate_limit_sms_send)
async def send_code(request: Request, c: CacheService = Depends(cache)):
    body = await _json_body(request)
    phone = str(body.get("phone") or "").strip()
    if not _PHONE_RE.match(phone):
        return JSONResponse({"error": "手机号格式不正确"}, status_code=400)

    if await c.client.get(_resend_key(phone)):
        return JSONResponse({"error": "发送太频繁，请稍后再试"}, status_code=429)

    code = "".join(secrets.choice("0123456789") for _ in range(settings.sms_code_length))
    await c.client.set(_code_key(phone), code, ex=settings.sms_code_expire_seconds)
    await c.client.set(_resend_key(phone), "1", ex=settings.sms_resend_interval_seconds)

    ok = await run_in_threadpool(send_sms, phone, code)
    if not ok:
        return JSONResponse({"error": "验证码发送失败，请稍后重试"}, status_code=502)
    return {"error": ""}


@router.post("/login")
@limiter.limit(settings.rate_limit_login)
async def login(request: Request, c: CacheService = Depends(cache), session: AsyncSession = Depends(db_session)):
    body = await _json_body(request)
    phone = str(body.get("phone") or "").strip()
    code = str(body.get("code") or "").strip()
    if not _PHONE_RE.match(phone) or not code:
        return JSONResponse({"error": "请输入手机号和验证码"}, status_code=400)

    saved = await c.client.get(_code_key(phone))
    if not saved or saved != code:
        return JSONResponse({"error": "验证码错误或已过期"}, status_code=401)
    await c.client.delete(_code_key(phone))

    user = await users_repo.get_or_create_by_phone(session, phone)
    token = create_access_token(phone, typ="visitor", expire_minutes=settings.visitor_jwt_expire_minutes, sty="phone")
    return {"access_token": token, "token_type": "bearer", "phone": user["phone"]}


@router.get("/me")
async def me(payload: dict = Depends(require_visitor_payload), session: AsyncSession = Depends(db_session)):
    """当前访客账号信息。sty 字段直接路由到对应查询，避免串行三次 DB 查询。"""
    sub = payload["sub"]
    sty = payload.get("sty", "phone")  # 旧 token 无 sty 时降级为 phone

    if sty == "wechat":
        user = await users_repo.get_by_openid(session, sub)
        if user:
            return {
                "login_type": "wechat", "phone": None,
                "nickname": user.get("nickname"), "created_at": user["created_at"],
            }
    elif sty == "email":
        user = await users_repo.get_by_email(session, sub)
        if user:
            return {
                "login_type": "email", "phone": None, "email": user["email"],
                "nickname": user.get("nickname"), "created_at": user["created_at"],
            }
    else:
        user = await users_repo.get_by_phone(session, sub)
        if user:
            return {
                "login_type": "phone", "phone": user["phone"],
                "nickname": user.get("nickname"), "created_at": user["created_at"],
            }
    return JSONResponse({"error": "用户不存在"}, status_code=404)


@router.post("/nickname")
async def set_nickname(
    request: Request, sub: str = Depends(require_visitor), session: AsyncSession = Depends(db_session)
):
    """用户自己设置昵称（微信个人订阅号拿不到网页授权/用户信息接口，无法自动取昵称）。"""
    body = await _json_body(request)
    nickname = str(body.get("nickname") or "").strip()
    if not nickname or len(nickname) > 20:
        return JSONResponse({"error": "昵称长度需在 1-20 字符之间"}, status_code=400)
    await users_repo.set_nickname(session, sub, nickname)
    return {"error": "", "nickname": nickname}


# ===== 邮箱注册 + 账密登录 =====

@router.post("/email/send-code")
@limiter.limit(settings.rate_limit_email_send)
async def email_send_code(request: Request, c: CacheService = Depends(cache), session: AsyncSession = Depends(db_session)):
    body = await _json_body(request)
    email = str(body.get("email") or "").strip().lower()
    if not _EMAIL_RE.match(email):
        return JSONResponse({"error": "邮箱格式不正确"}, status_code=400)
    if await users_repo.get_by_email(session, email):
        return JSONResponse({"error": "该邮箱已注册，请直接登录"}, status_code=400)

    if await c.client.get(_email_resend_key(email)):
        return JSONResponse({"error": "发送太频繁，请稍后再试"}, status_code=429)

    code = "".join(secrets.choice("0123456789") for _ in range(6))
    await c.client.set(_email_code_key(email), code, ex=settings.email_code_expire_seconds)
    await c.client.set(_email_resend_key(email), "1", ex=settings.email_resend_interval_seconds)

    ok = await run_in_threadpool(send_verification_email, email, code)
    if not ok:
        return JSONResponse({"error": "验证码发送失败，请稍后重试"}, status_code=502)
    return {"error": ""}


@router.post("/email/register")
@limiter.limit(settings.rate_limit_login)
async def email_register(request: Request, c: CacheService = Depends(cache), session: AsyncSession = Depends(db_session)):
    body = await _json_body(request)
    email = str(body.get("email") or "").strip().lower()
    code = str(body.get("code") or "").strip()
    password = str(body.get("password") or "")
    if not _EMAIL_RE.match(email) or not code:
        return JSONResponse({"error": "请输入邮箱和验证码"}, status_code=400)
    if len(password) < 6:
        return JSONResponse({"error": "密码至少 6 位"}, status_code=400)

    saved = await c.client.get(_email_code_key(email))
    if not saved or saved != code:
        return JSONResponse({"error": "验证码错误或已过期"}, status_code=401)
    await c.client.delete(_email_code_key(email))

    user = await users_repo.create_by_email(session, email, hash_password(password))
    if not user:
        return JSONResponse({"error": "该邮箱已注册，请直接登录"}, status_code=400)
    token = create_access_token(email, typ="visitor", expire_minutes=settings.visitor_jwt_expire_minutes, sty="email")
    resp: dict = {"access_token": token, "token_type": "bearer", "email": email}
    if user.get("is_admin"):
        resp["admin_token"] = create_access_token(email, typ="admin", expire_minutes=settings.jwt_expire_minutes)
    return resp


@router.post("/email/login")
@limiter.limit(settings.rate_limit_login)
async def email_login(request: Request, session: AsyncSession = Depends(db_session)):
    body = await _json_body(request)
    email = str(body.get("email") or "").strip().lower()
    password = str(body.get("password") or "")
    if not _EMAIL_RE.match(email) or not password:
        return JSONResponse({"error": "请输入邮箱和密码"}, status_code=400)

    user = await users_repo.get_by_email(session, email)
    if not user or not user.get("password_hash") or not verify_password(password, user["password_hash"]):
        return JSONResponse({"error": "邮箱或密码错误"}, status_code=401)

    token = create_access_token(email, typ="visitor", expire_minutes=settings.visitor_jwt_expire_minutes, sty="email")
    resp: dict = {"access_token": token, "token_type": "bearer", "email": email}
    if user.get("is_admin"):
        resp["admin_token"] = create_access_token(email, typ="admin", expire_minutes=settings.jwt_expire_minutes)
    return resp


# ===== 微信扫码 =====

@router.get("/wechat/qrcode")
async def wechat_qrcode(c: CacheService = Depends(cache)):
    scene_id = random.randint(1, 2147483647)
    scene_key = str(scene_id)
    access_token = await _wx_access_token(c.client)
    ticket = await run_in_threadpool(wechat.create_qrcode_ticket, access_token, scene_id)
    await c.client.set(f"{_WX_SCENE_PREFIX}{scene_key}", "pending", ex=_WX_SCENE_EXPIRE)
    return {"scene_key": scene_key, "qr_url": wechat.ticket_to_url(ticket)}


@router.get("/wechat/webhook")
async def wechat_webhook_verify(
    signature: str = "", timestamp: str = "", nonce: str = "", echostr: str = ""
):
    """微信服务器接入验证（GET）。"""
    if wechat.verify_signature(settings.wechat_token, signature, timestamp, nonce):
        return PlainTextResponse(echostr)
    return JSONResponse({"error": "invalid signature"}, status_code=403)


_WX_MSGCODE_PREFIX = "wx:msgcode:"
_WX_MSGCODE_EXPIRE = 300


@router.post("/wechat/webhook")
async def wechat_webhook_event(
    request: Request,
    signature: str = "",
    timestamp: str = "",
    nonce: str = "",
    c: CacheService = Depends(cache),
    session: AsyncSession = Depends(db_session),
):
    """微信事件推送（POST）：文本消息发验证码 / subscribe / SCAN。"""
    if not wechat.verify_signature(settings.wechat_token, signature, timestamp, nonce):
        return PlainTextResponse("", status_code=403)

    body = await request.body()
    event = wechat.parse_xml_event(body)
    import logging as _log; _log.getLogger("app.wechat").info("wx event: %s", event)
    msg_type = event.get("MsgType", "")
    openid = event.get("FromUserName", "")
    mp_id = event.get("ToUserName", "")

    # 用户发任意文本消息 OR 点击菜单"获取验证码"按钮 → 生成验证码回复
    evt = event.get("Event", "")
    is_click_get_code = msg_type == "event" and evt == "CLICK" and event.get("EventKey", "") == "GET_CODE"
    if (msg_type == "text" or is_click_get_code) and openid:
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        await c.client.set(f"{_WX_MSGCODE_PREFIX}{code}", openid, ex=_WX_MSGCODE_EXPIRE)
        reply = wechat.build_text_reply(openid, mp_id, f"您的登录验证码是 {code}，5分钟内有效。")
        return PlainTextResponse(reply, media_type="application/xml")

    # 扫码关注 / 扫码已关注事件（保留兼容）
    evt = event.get("Event", "")
    if msg_type == "event" and evt in ("subscribe", "SCAN") and openid:
        scene_key = ""
        if evt == "SCAN":
            scene_key = event.get("EventKey", "")
        elif evt == "subscribe":
            ek = event.get("EventKey", "")
            if ek.startswith("qrscene_"):
                scene_key = ek[len("qrscene_"):]
        if scene_key and await c.client.get(f"{_WX_SCENE_PREFIX}{scene_key}") == "pending":
            await users_repo.get_or_create_by_openid(session, openid)
            token = create_access_token(openid, typ="visitor", expire_minutes=settings.visitor_jwt_expire_minutes, sty="wechat")
            await c.client.set(f"{_WX_SCENE_PREFIX}{scene_key}", token, ex=_WX_SCENE_EXPIRE)

    return PlainTextResponse("success")


@router.post("/wechat/code-login")
@limiter.limit(settings.rate_limit_login)
async def wechat_code_login(
    request: Request,
    c: CacheService = Depends(cache),
    session: AsyncSession = Depends(db_session),
):
    """用户凭微信回复的验证码换取 JWT。"""
    body = await _json_body(request)
    code = str(body.get("code") or "").strip()
    if not code:
        return JSONResponse({"error": "请输入验证码"}, status_code=400)

    openid = await c.client.get(f"{_WX_MSGCODE_PREFIX}{code}")
    if not openid:
        return JSONResponse({"error": "验证码错误或已过期"}, status_code=401)
    await c.client.delete(f"{_WX_MSGCODE_PREFIX}{code}")

    await users_repo.get_or_create_by_openid(session, openid)
    token = create_access_token(openid, typ="visitor", expire_minutes=settings.visitor_jwt_expire_minutes, sty="wechat")
    return {"access_token": token, "token_type": "bearer"}


@router.get("/wechat/poll/{scene_key}")
async def wechat_poll(scene_key: str, c: CacheService = Depends(cache)):
    val = await c.client.get(f"{_WX_SCENE_PREFIX}{scene_key}")
    if not val or val == "pending":
        return {"status": "pending"}
    return {"status": "scanned", "access_token": val}


# ===== auth/config =====

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else ""


@auth_config_router.get("/config")
async def auth_config(c: CacheService = Depends(cache), session: AsyncSession = Depends(db_session)):
    """前端启动时查询：访客模式是否开启（始终要求登录）。不加守卫，必须开放。"""
    visitor_mode = await _is_visitor_mode_enabled(c, session)
    return {"require_login": True, "visitor_mode": visitor_mode}


# ===== 游客一键登录 =====

@router.post("/guest-login")
async def guest_login(c: CacheService = Depends(cache), session: AsyncSession = Depends(db_session)):
    """游客一键登录：仅在访客模式开启时可用，发放只读 JWT（sty=guest，TTL=24h）。"""
    if not await _is_visitor_mode_enabled(c, session):
        return JSONResponse({"error": "访客模式已关闭，请使用账号登录"}, status_code=403)
    token = create_access_token("guest", typ="visitor", expire_minutes=60 * 24, sty="guest")
    return {"access_token": token, "token_type": "bearer"}

