"""posts 表：镜像旧 db.py SCHEMA（含 images / image_desc 两列）。"""
from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String, primary_key=True)          # 雪球 status id
    user_id: Mapped[str | None] = mapped_column(String)
    user_name: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[int | None] = mapped_column(BigInteger)          # 毫秒时间戳
    date: Mapped[str | None] = mapped_column(String)                   # YYYY-MM-DD
    text: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    retweet_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    fav_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_json: Mapped[str | None] = mapped_column(Text)
    images: Mapped[str | None] = mapped_column(Text)                   # JSON 数组：配图URL列表
    image_desc: Mapped[str | None] = mapped_column(Text)               # 视觉模型描述缓存
    brief: Mapped[str | None] = mapped_column(Text)                    # AI一句话总结（长帖抓取时自动生成）
    fetched_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (Index("idx_posts_user_date", "user_id", "date"),)
