"""users 表（Phase 9）：访客账号，手机号+验证码登录。"""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    openid: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    nickname: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[int | None] = mapped_column(BigInteger)
