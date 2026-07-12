"""邮箱验证码发送（访客账号系统）。

真实 SMTP 实现（邮箱不需要短信那种资质认证，配一个 SMTP 账号即可）。
SMTP_HOST 未配置时退化为 Mock（只打日志，不真实发送），方便本地开发不用真配邮箱。
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("app.email")

_BRAND = "雪球看板 Xueqiu Insight"

_TEXT_TEMPLATE = """{brand}

您正在注册/登录账号，验证码：{code}

该验证码 {minutes} 分钟内有效，请勿泄露给他人。
如非本人操作，请忽略此邮件。

本邮件由系统自动发送，请勿直接回复。
"""

_HTML_TEMPLATE = """\
<div style="background:#f5f6f7;padding:32px 0;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;">
  <div style="max-width:480px;margin:0 auto;background:#ffffff;border-radius:8px;overflow:hidden;">
    <div style="background:#1677ff;padding:20px 32px;">
      <span style="color:#fff;font-size:16px;font-weight:600;">{brand}</span>
    </div>
    <div style="padding:32px;">
      <p style="font-size:14px;color:#333;margin:0 0 16px;">您好，</p>
      <p style="font-size:14px;color:#333;margin:0 0 24px;">您正在注册/登录账号，本次验证码为：</p>
      <div style="background:#f5f6f7;border-radius:6px;padding:16px 0;text-align:center;margin-bottom:24px;">
        <span style="font-size:32px;letter-spacing:8px;font-weight:700;color:#1677ff;">{code}</span>
      </div>
      <p style="font-size:13px;color:#888;margin:0 0 8px;">验证码 {minutes} 分钟内有效，请勿泄露给他人。</p>
      <p style="font-size:13px;color:#888;margin:0;">如非本人操作，请忽略此邮件。</p>
    </div>
    <div style="padding:16px 32px;background:#fafafa;border-top:1px solid #eee;">
      <p style="font-size:12px;color:#aaa;margin:0;">本邮件由系统自动发送，请勿直接回复。</p>
    </div>
  </div>
</div>
"""


def send_verification_email(to_addr: str, code: str) -> bool:
    """发送注册验证码邮件；返回是否发送成功。"""
    minutes = settings.email_code_expire_seconds // 60
    if not settings.smtp_host:
        logger.info("[MOCK EMAIL] 发送验证码到 %s: %s", to_addr, code)
        return True

    from_addr = settings.smtp_from or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(_TEXT_TEMPLATE.format(brand=_BRAND, code=code, minutes=minutes), "plain", "utf-8"))
    msg.attach(MIMEText(_HTML_TEMPLATE.format(brand=_BRAND, code=code, minutes=minutes), "html", "utf-8"))
    msg["Subject"] = f"【{_BRAND}】您的验证码是 {code}"
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
    except Exception:
        logger.exception("发送验证码邮件失败: %s", to_addr)
        return False
