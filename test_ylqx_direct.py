import sys
sys.path.insert(0, 'backend')
from app.repositories import sync_data as db

sector = "医疗器械"
print(f"测试板块: {sector}")
print(f"get_board_code('{sector}') = {db.get_board_code(sector)}")

cached = db.get_sector_members_cached(sector)
print(f"get_sector_members_cached('{sector}') = {cached}")

if cached:
    print(f"  缓存成分股数量: {len(cached)}")
    print(f"  前10只: {cached[:10]}")
else:
    print("  缓存为空或过期")

# 直接查数据库
from app.core.sync_db import sync_session
from sqlalchemy import text
with sync_session() as s:
    count = s.execute(text("SELECT COUNT(*) FROM stock_sector WHERE sector = :s"), {"s": sector}).scalar()
    print(f"\nstock_sector表中实际记录数: {count}")

    if count > 0:
        sample = s.execute(text("SELECT code, updated_at FROM stock_sector WHERE sector = :s LIMIT 5"), {"s": sector}).fetchall()
        print(f"前5条记录:")
        for code, ts in sample:
            from datetime import datetime
            dt = datetime.fromtimestamp(ts) if ts else None
            print(f"  {code} (更新于 {dt})")
