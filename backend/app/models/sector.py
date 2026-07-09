"""板块：sector_catalog（名录）+ stock_sector（成分股缓存，7天有效期由上层判断）。"""
from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SectorCatalog(Base):
    __tablename__ = "sector_catalog"

    board_code: Mapped[str] = mapped_column(String, primary_key=True)   # 新浪 gn_xxx / hangye_xxx
    name: Mapped[str | None] = mapped_column(String, unique=True)
    kind: Mapped[str | None] = mapped_column(String)                   # 'industry' | 'concept'
    updated_at: Mapped[int | None] = mapped_column(BigInteger)


class StockSector(Base):
    __tablename__ = "stock_sector"

    # 原表仅 UNIQUE(code, sector)，用其作复合主键。
    code: Mapped[str] = mapped_column(String, primary_key=True)
    sector: Mapped[str] = mapped_column(String, primary_key=True)       # 对应 sector_catalog.name
    board_code: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        Index("idx_stock_sector_sector", "sector"),
        Index("idx_stock_sector_code", "code"),
    )
