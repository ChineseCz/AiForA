import sys
sys.path.insert(0, '/app')

from app.services import matching
from app.repositories import sync_data as db

# 获取候选池（最新行情）
rows = db.get_latest_rows()
print(f"候选池股票数: {len(rows)}")

# 测试行业板块筛选
industry_rows = matching.match_sector(rows, ["房地产业"])
print(f"\n筛选'房地产业'(行业): {len(industry_rows)} 只")
if industry_rows:
    print(f"前3只: {[(r['code'], r['name']) for r in industry_rows[:3]]}")

# 测试概念板块筛选
concept_rows = matching.match_sector(rows, ["大健康"])
print(f"\n筛选'大健康'(概念): {len(concept_rows)} 只")
if concept_rows:
    print(f"前3只: {[(r['code'], r['name']) for r in concept_rows[:3]]}")
