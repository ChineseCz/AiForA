import sys
sys.path.insert(0, 'backend')
from app.repositories import sync_data as db

sector = "医疗器械"
print(f"板块名: {sector}")
print(f"get_board_code() = {db.get_board_code(sector)}")
print(f"get_sector_members_cached() = {db.get_sector_members_cached(sector)}")

# 检查数据库里这个板块是否存在
from app.core.sync_db import sync_session
from sqlalchemy import text
with sync_session() as s:
    row = s.execute(text("SELECT name, board_code, kind FROM sector_catalog WHERE name = :n"), {"n": sector}).fetchone()
    print(f"sector_catalog 记录: {row}")

    if row:
        board_code = row[1]
        cached = s.execute(text("SELECT codes FROM sector_members WHERE sector = :n OR board_code = :bc"), {"n": sector, "bc": board_code}).fetchone()
        print(f"sector_members 缓存: {cached}")
        if cached:
            codes = cached[0].split(',') if cached[0] else []
            print(f"  成分股数量: {len(codes)}")
            print(f"  前5只: {codes[:5]}")
