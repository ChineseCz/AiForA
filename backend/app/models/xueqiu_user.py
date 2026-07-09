"""xueqiu_users 表（新增）：管理员维护的「大V采集名单」。

取代旧 .env 的 XUEQIU_USERS。语义是「要抓谁」，与 /api/users（从 posts 取「已抓到谁」）不同。
Phase 1 仅建表 + 迁移时 seed；Phase 2 由抓取任务与管理员接口消费。
"""
from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class XueqiuUser(Base):
    __tablename__ = "xueqiu_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, unique=True)   # 雪球 uid 或原始配置串（url/昵称）
    name: Mapped[str | None] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[int | None] = mapped_column(BigInteger)
