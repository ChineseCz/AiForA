import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.repositories import sync_data as db

result = db.get_sectors_by_code("300556")
print(f"查询结果数量: {len(result)}")
if result:
    print(f"前3条: {result[:3]}")
else:
    print("返回空列表")
