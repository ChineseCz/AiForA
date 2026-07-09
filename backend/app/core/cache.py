"""Redis 缓存层（redis.asyncio）。

失效策略：全局数据版本号 dataver。key 里嵌入当前 dataver；每次数据同步（Phase 2）调用
invalidate_all() = 一次 INCR，旧 key 立即不可达并靠 TTL 自然过期，热路径无 SCAN/KEYS。
"""
import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings

_client: aioredis.Redis | None = None
_DATAVER_KEY = "natapp:dataver"


def get_client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class CacheService:
    """薄封装：get/set json + dataver 版本 + 失效。缓存故障一律降级（返回 miss/静默）。"""

    def __init__(self, client: aioredis.Redis):
        self.client = client

    async def version(self) -> int:
        try:
            v = await self.client.get(_DATAVER_KEY)
            return int(v) if v else 1
        except Exception:
            return 1

    async def invalidate_all(self) -> int:
        """数据同步后调用：版本号 +1，所有旧缓存作废。"""
        try:
            return await self.client.incr(_DATAVER_KEY)
        except Exception:
            return 0

    @staticmethod
    def _argsig(args: dict[str, Any]) -> str:
        raw = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    async def key(self, endpoint: str, **args: Any) -> str:
        ver = await self.version()
        return f"natapp:v{ver}:{endpoint}:{self._argsig(args)}"

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self.client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            return None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        try:
            await self.client.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl)
        except Exception:
            pass


def get_cache() -> CacheService:
    return CacheService(get_client())


def bump_dataver_sync() -> int:
    """同步版失效：供 Celery 任务在数据同步完成后调用（一次 INCR）。失败降级不抛。"""
    try:
        import redis as sync_redis
        client = sync_redis.from_url(settings.redis_url, decode_responses=True)
        try:
            return client.incr(_DATAVER_KEY)
        finally:
            client.close()
    except Exception:
        return 0
