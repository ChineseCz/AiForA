"""短信验证码发送（访客账号系统）。

当前为 Mock 实现：只打日志，不真实发送。用户注册好阿里云/腾讯云短信服务后，
替换 send_sms 函数体为真实 SDK 调用即可，调用方（user_auth 路由）无需改动。
"""
import logging

logger = logging.getLogger("app.sms")


def send_sms(phone: str, code: str) -> bool:
    """发送验证码短信；返回是否发送成功。Mock 实现：记录日志后直接返回 True。"""
    logger.info("[MOCK SMS] 发送验证码到 %s: %s", phone, code)
    return True
