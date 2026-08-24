"""检查数据库中的 ETF 记录"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.repositories import sync_data as db

# 常见 ETF
TEST_ETFS = ["510300", "159915", "512880", "510500", "159919"]

print("=" * 60)
print("检查数据库中的 ETF 记录")
print("=" * 60)

all_rows = db.get_latest_rows()
rows_by_code = {r['code']: r for r in all_rows}

for code in TEST_ETFS:
    row = rows_by_code.get(code)
    if row:
        print(f"✅ {code} {row['name']}: {row['close']}")
    else:
        print(f"❌ {code}: 不存在")

print("\n" + "=" * 60)
print("统计数据库总记录")
print("=" * 60)
rows = db.get_latest_rows()
print(f"总数: {len(rows)} 条")

# 按代码前缀统计
etf_count = sum(1 for r in rows if r['code'].startswith(('51', '15')))
stock_count = len(rows) - etf_count
print(f"  A股: {stock_count} 条")
print(f"  ETF: {etf_count} 条")
