"""自选股买卖信号通知：扫描、去重和发送。"""
import json
import logging
import time

from sqlalchemy import text

from app.core.config import settings
from app.core.sync_db import sync_session

logger = logging.getLogger("app.notifications")


def _get_settings(user_id: str) -> dict:
    defaults = {"signal_enabled": True, "email_enabled": True, "wechat_enabled": False}
    with sync_session() as s:
        raw = s.execute(text("SELECT value_json FROM user_settings WHERE user_id=:u AND key='notification_settings'"), {"u": user_id}).scalar()
    try:
        value = json.loads(raw) if raw else {}
        return {**defaults, **value} if isinstance(value, dict) else defaults
    except (TypeError, ValueError):
        return defaults


def _claim(user_id: str, channel: str, event_key: str) -> bool:
    with sync_session() as s:
        row = s.execute(text(
            "INSERT INTO notification_events (user_id, channel, event_key, sent_at, status) "
            "VALUES (:u, :c, :e, :t, 'pending') "
            "ON CONFLICT (user_id, channel, event_key) DO UPDATE SET status='pending', error='', sent_at=EXCLUDED.sent_at "
            "WHERE notification_events.status='error' RETURNING id"
        ), {"u": user_id, "c": channel, "e": event_key, "t": int(time.time())}).first()
        return row is not None


def _finish(user_id: str, channel: str, event_key: str, status: str, error: str = "") -> None:
    with sync_session() as s:
        s.execute(text(
            "UPDATE notification_events SET status=:s, error=:e, sent_at=:t "
            "WHERE user_id=:u AND channel=:c AND event_key=:k"
        ), {"u": user_id, "c": channel, "k": event_key, "s": status, "e": error[:1000], "t": int(time.time())})


def _send_email(to_addr: str, subject: str, content: str) -> bool:
    if not settings.smtp_host:
        logger.info("[MOCK EMAIL] signal notification to %s: %s", to_addr, subject)
        return True
    import smtplib
    from email.mime.text import MIMEText
    from_addr = settings.smtp_from or settings.smtp_user
    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(from_addr, [to_addr], msg.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(from_addr, [to_addr], msg.as_string())
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("signal email failed: %s", to_addr)
        return False


def _send_wechat(openid: str, title: str, content: str, url: str = "") -> tuple[bool, str]:
    template_id = getattr(settings, "wechat_notify_template_id", "")
    if not template_id:
        return False, "未配置 WECHAT_NOTIFY_TEMPLATE_ID"
    from app.services.external import wechat
    try:
        token = wechat.fetch_access_token(settings.wechat_appid, settings.wechat_appsecret)
        result = wechat.send_template_message(token, openid, template_id, {
            "first": {"value": title},
            "keyword1": {"value": content[:200]},
            "remark": {"value": "雪球看板提醒"},
        }, url)
        if result.get("errcode", 0) != 0:
            return False, str(result)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def scan_signal_notifications() -> int:
    """扫描所有登录用户的自选股，只对当天新出现的信号发送一次。"""
    from app.repositories import sync_data as db
    from app.services import views
    with sync_session() as s:
        users = s.execute(text("SELECT DISTINCT user_id FROM stock_groups WHERE user_id IS NOT NULL")).scalars().all()
        rows = s.execute(text(
            "SELECT g.user_id, m.code, m.name FROM stock_groups g JOIN stock_group_members m ON m.group_id=g.id "
            "WHERE g.user_id IS NOT NULL AND g.is_paper=FALSE"
        )).mappings().all()
    codes_by_user: dict[str, list[dict]] = {}
    for row in rows:
        codes_by_user.setdefault(row["user_id"], []).append(dict(row))
    total = 0
    for user_id in users:
        cfg = _get_settings(user_id)
        if not cfg.get("signal_enabled", False):
            continue
        channels = [c for c in ("email", "wechat") if cfg.get(f"{c}_enabled", False)]
        if not channels:
            continue
        for member in codes_by_user.get(user_id, []):
            try:
                view = views.get_kline_view(member["code"], period="day")
                bar = (view.get("bars") or [])[-1]
                signals = []
                for key, label in (("strict_ok", "严格买点"), ("loose_ok", "宽松买点"), ("golden_ok", "金叉买点"), ("mid_reverse_ok", "中期反转卖点"), ("stop_loss_ok", "止损卖点")):
                    if bar.get(key): signals.append(label)
                if not signals:
                    continue
                event_key = f"{bar.get('trade_date')}:{member['code']}:{','.join(signals)}"
                content = f"{member.get('name') or view.get('name') or member['code']}（{member['code']}）\n交易日：{bar.get('trade_date')}\n信号：{'、'.join(signals)}"
                for channel in channels:
                    if not _claim(user_id, channel, event_key):
                        continue
                    ok, error = False, ""
                    if channel == "email":
                        with sync_session() as s:
                            addr = s.execute(text("SELECT email FROM users WHERE email=:u OR phone=:u OR openid=:u"), {"u": user_id}).scalar()
                        ok = bool(addr) and _send_email(addr, f"【雪球看板】自选股信号提醒：{member['code']}", content)
                        error = "用户未绑定邮箱或发送失败" if not ok else ""
                    else:
                        with sync_session() as s:
                            openid = s.execute(text("SELECT openid FROM users WHERE email=:u OR phone=:u OR openid=:u"), {"u": user_id}).scalar()
                        ok, error = (False, "用户未绑定微信") if not openid else _send_wechat(openid, f"自选股信号：{member['code']}", content)
                    _finish(user_id, channel, event_key, "sent" if ok else "error", error)
                    total += int(ok)
            except Exception as exc:  # noqa: BLE001
                logger.exception("scan signal failed for %s", member.get("code"))
    return total
