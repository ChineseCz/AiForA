"""admins 表（Phase 3）：管理员账号，用于后台写/触发接口鉴权。"""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[int | None] = mapped_column(BigInteger)
