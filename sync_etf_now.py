"""直接同步 ETF 到数据库（完整版本）"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services import ingest

print("=" * 60)
print("开始同步 A股 + ETF 快照")
print("=" * 60)

total = ingest.sync_daily_snapshot()

print(f"\n✅ 同步完成，共 {total} 条记录")
