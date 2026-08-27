"""集中配置：pydantic-settings 从环境变量 / .env 读取。

对应旧 config.py 的每一项，1:1 迁移；密钥只留 env，不入库。
数据库/Redis/池大小/缓存 TTL 等基础设施项是新增的。
"""
import sys
from functools import lru_cache

from pydantic import model_validator
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
    relay_api_image_key: str = ""  # 生图/视觉模型专用 key；空则回退到 relay_api_key

    # ===== 雪球（抓取参数，Phase 2 宿主 worker 用）=====
    xueqiu_cookie: str = ""
    max_pages: int = 10
    fetch_full_text: bool = True
    request_delay: float = 1.5
    headless: bool = False
    browser_channel: str = "msedge"  # Linux 服务器设为空字符串以使用 Chromium
    # 帖子正文超过这个字数才在抓取后自动生成一句话总结（brief），短帖子直接全文展示不用调LLM
    post_brief_min_length: int = 200

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
    # 个股AI分析：按 code+trade_date 缓存，同一交易日内多次访问/多用户共享同一份结果，
    # 不随 dataver 版本失效（全市场10分钟同步会频繁 bump dataver，若跟着它失效会导致刚生成
    # 的分析很快被冲掉，被迫重新调用LLM），靠 TTL 自然过期 + trade_date 变化后 key 自动不同。
    cache_ttl_ai_analysis: int = 43200  # 12小时，覆盖单个交易日剩余时段

    # ===== CORS（Phase 4 前端用）=====
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ===== 管理员鉴权（Phase 3）=====
    jwt_secret: str = "change-me-in-production"  # 生产务必用强随机值（env 覆盖）
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 未勾选免登录时 24 小时
    remember_jwt_expire_minutes: int = 43200  # 勾选“30日内免登录”时 30 天
    # 启动引导管理员：admins 表为空且这两项都配置时，自动创建一个管理员
    admin_username: str = ""
    admin_password: str = ""

    # ===== 限流（Phase 3，slowapi + Redis 存储，多实例共享）=====
    rate_limit_enabled: bool = True
    rate_limit_public: str = "120/minute"   # 公开只读接口默认限额（按 IP）
    rate_limit_login: str = "5/minute"      # 登录接口更严（防爆破）
    rate_limit_sms_send: str = "1/minute"   # 发送验证码接口（按 IP，配合 Redis 按手机号节流）
    rate_limit_email_send: str = "3/minute"  # 邮箱验证码发送接口（按 IP，配合 Redis 按邮箱节流）

    # ===== 访客账号（手机号+验证码）=====
    sms_code_length: int = 6
    sms_code_expire_seconds: int = 300      # 验证码有效期 5 分钟
    sms_resend_interval_seconds: int = 60   # 同一手机号重发间隔
    visitor_jwt_expire_minutes: int = 1440  # 未勾选免登录时 24 小时

    # ===== 邮箱账号（注册验证码 + 账密登录）=====
    email_code_expire_seconds: int = 600     # 注册验证码有效期 10 分钟
    email_resend_interval_seconds: int = 20  # 同一邮箱重发间隔，配合接口限流约1分钟3次
    captcha_expire_seconds: int = 300  # 图片验证码有效期 5 分钟
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""       # 发件人显示地址；空则用 smtp_user
    smtp_use_ssl: bool = True

    # ===== 微信公众号（扫码登录）=====
    wechat_appid: str = ""
    wechat_appsecret: str = ""
    # 与公众平台"服务器配置"里填写的 Token 保持一致
    wechat_token: str = ""
    wechat_notify_template_id: str = ""

    @model_validator(mode="after")
    def _check_jwt_secret(self) -> "Settings":
        default = "change-me-in-production"
        if self.jwt_secret == default:
            # 本地开发（database_url 包含 localhost）允许默认值，仅打警告；生产环境强制退出。
            if "localhost" not in self.database_url and "127.0.0.1" not in self.database_url:
                print(
                    "[FATAL] JWT_SECRET 未配置或仍为默认值，生产环境禁止使用！"
                    " 请在 .env 中设置 JWT_SECRET=<随机强密钥>",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(
                "[WARN] JWT_SECRET 使用默认值，仅允许本地开发环境。生产部署前必须修改！",
                file=sys.stderr,
            )
        return self

    @property
    def effective_vision_model(self) -> str:
        return self.vision_model or self.relay_model

    @property
    def effective_image_key(self) -> str:
        return self.relay_api_image_key or self.relay_api_key

    @property
    def database_url_sync(self) -> str:
        """给同步引擎用：把 asyncpg 驱动换成 psycopg。"""
        return self.database_url.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
