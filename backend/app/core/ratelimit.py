"""限流（Phase 3）：slowapi + Redis 存储，多 API 实例共享计数（横向扩展前提）。

- 默认限额（default_limits）经 SlowAPIMiddleware 施加到所有路由（按客户端 IP）。
- 登录接口用 @limiter.limit 覆盖为更严限额（防爆破）。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# headers_enabled=False：不往响应注入 X-RateLimit-* 头（那要求每个被装饰的端点声明
# response: Response 参数）。限流本身照常生效，超限仍返回 429。
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=[settings.rate_limit_public] if settings.rate_limit_enabled else [],
    enabled=settings.rate_limit_enabled,
    headers_enabled=False,
)
