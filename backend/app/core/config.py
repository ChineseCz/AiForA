"""集中配置：pydantic-settings 从环境变量 / .env 读取。

对应旧 config.py 的每一项，1:1 迁移；密钥只留 env，不入库。
数据库/Redis/池大小/缓存 TTL 等基础设施项是新增的。
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===== 基础设施 =====
    # 异步 API 用（asyncpg）；迁移脚本用同一库但走 psycopg（见 database_url_sync）。
    database_url: str = "postgresql+asyncpg://natapp:natapp@localhost:5432/natapp"
    redis_url: str = "redis://localhost:6379/0"

    # 连接池：千人并发下异步请求 await 非占连接，热路径走 Redis，池 20~30 足够。
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800
    db_statement_timeout_ms: int = 15000
    # 重计算（选股/K线）专用同步小池。
    sync_db_pool_size: int = 4
    sync_db_max_overflow: int = 4

    # ===== 中转站 API（对应旧 config）=====
    relay_api_key: str = ""
    relay_api_url: str = "https://www.micuapi.ai/v1"
    relay_model: str = "gpt-5.4-mini"
    vision_model: str = ""  # 空则沿用 relay_model

    # ===== 雪球（抓取参数，Phase 2 宿主 worker 用）=====
    xueqiu_cookie: str = ""
    max_pages: int = 10
    fetch_full_text: bool = True
    request_delay: float = 1.5
    headless: bool = False

    # ===== 路径（宿主 worker / 迁移脚本用）=====
    data_dir: str = "./data"
    profile_dir: str = ""  # 空则 data_dir/edge_profile
    reports_dir: str = "./reports"

    # ===== 缓存 TTL（秒）=====
    cache_ttl_overview: int = 300
    cache_ttl_posts: int = 60
    cache_ttl_summary: int = 3600
    cache_ttl_summary_keys: int = 300
    cache_ttl_screen: int = 180
    cache_ttl_kline: int = 300
    cache_ttl_fundamentals: int = 300
    cache_ttl_sectors: int = 3600
    cache_ttl_news: int = 900
    cache_ttl_quote: int = 1  # 秒级轮询：短TTL，多用户同时看同一只股票也只打一次上游

    # ===== CORS（Phase 4 前端用）=====
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ===== 管理员鉴权（Phase 3）=====
    jwt_secret: str = "change-me-in-production"  # 生产务必用强随机值（env 覆盖）
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720  # 12 小时
    # 启动引导管理员：admins 表为空且这两项都配置时，自动创建一个管理员
    admin_username: str = ""
    admin_password: str = ""

    # ===== 限流（Phase 3，slowapi + Redis 存储，多实例共享）=====
    rate_limit_enabled: bool = True
    rate_limit_public: str = "120/minute"   # 公开只读接口默认限额（按 IP）
    rate_limit_login: str = "5/minute"      # 登录接口更严（防爆破）

    @property
    def effective_vision_model(self) -> str:
        return self.vision_model or self.relay_model

    @property
    def database_url_sync(self) -> str:
        """给同步引擎用：把 asyncpg 驱动换成 psycopg。"""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
