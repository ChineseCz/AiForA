"""导出全部模型，供 Alembic 的 target_metadata 发现。"""
from app.models.admin import Admin
from app.models.base import Base
from app.models.group import StockGroup, StockGroupMember
from app.models.indicator import StockIndicator
from app.models.job_run import JobRun
from app.models.post import Post
from app.models.schedule import Schedule
from app.models.sector import SectorCatalog, StockSector
from app.models.stock_daily import StockDaily
from app.models.index_daily import IndexDaily
from app.models.bond_daily import BondDaily
from app.models.backfill_failure import BackfillFailure
from app.models.stock_finance import StockFinance
from app.models.summary import Summary
from app.models.user import User
from app.models.xueqiu_user import XueqiuUser

__all__ = [
    "Base",
    "Admin",
    "Post",
    "Summary",
    "StockDaily",
    "IndexDaily",
    "StockFinance",
    "StockGroup",
    "StockGroupMember",
    "StockIndicator",
    "SectorCatalog",
    "StockSector",
    "XueqiuUser",
    "Schedule",
    "JobRun",
    "User",
    "BackfillFailure",
]
