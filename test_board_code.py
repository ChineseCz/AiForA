from app.repositories import sync_data as db
from app.core.sync_db import sync_session
from sqlalchemy import text

# 测试精确匹配
print('精确匹配测试：')
print(f'  半导体 -> {db.get_board_code("半导体")}')
print(f'  医疗机械 -> {db.get_board_code("医疗机械")}')
print(f'  医疗器械 -> {db.get_board_code("医疗器械")}')

# 搜索相似的
with sync_session() as s:
    rows = s.execute(text("SELECT name, board_code FROM sector_catalog WHERE name LIKE '%半导体%' OR name LIKE '%医疗%'")).fetchall()
    print(f'\n包含半导体/医疗的板块：')
    for name, code in rows[:15]:
        print(f'  {name:30s} {code}')
