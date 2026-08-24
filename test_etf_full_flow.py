"""测试常用 ETF 的完整流程：写入快照 + 查询 + K线回补"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.external import sina
from app.repositories import sync_data as db
from datetime import date

# 常用 ETF：沪深300(510300)、创业板(159915)、证券ETF(512880)
TARGET_ETFS = ["510300", "159915", "512880"]

print("=" * 60)
print("步骤 1：拉取 ETF 快照并写入目标 ETF")
print("=" * 60)
all_etf_rows = sina.fetch_etf_snapshot()
target_rows = [row for row in all_etf_rows if row['code'] in TARGET_ETFS]

if len(target_rows) < len(TARGET_ETFS):
    print(f"⚠️ 只找到 {len(target_rows)} 只目标 ETF（预期 {len(TARGET_ETFS)}）")
else:
    print(f"✅ 找到全部 {len(target_rows)} 只目标 ETF")

trade_date = date.today().isoformat()
n = db.save_snapshot(trade_date, target_rows)
print(f"✅ 已写入 {n} 条快照")

for row in target_rows:
    print(f"  {row['code']} {row['name']}: {row['close']}")

print("\n" + "=" * 60)
print("步骤 2：查询验证")
print("=" * 60)
latest = db.get_latest_rows()
for code in TARGET_ETFS:
    found = [r for r in latest if r['code'] == code]
    if found:
        print(f"  ✅ {code} {found[0]['name']}")
    else:
        print(f"  ❌ {code} 未找到")

print("\n" + "=" * 60)
print("步骤 3：检查 K线缺失情况")
print("=" * 60)
for code in TARGET_ETFS:
    has_missing = db.has_missing_bars(code, 60)
    bar_count = len(db.get_history_for_code(code))
    print(f"  {code}: 共有 {bar_count} 根K线，{'需要回补' if has_missing else '数据完整'}")

print("\n完成测试")
