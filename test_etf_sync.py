"""测试 ETF 同步流程"""
import sys
import os

# 添加 backend 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.external import sina
from app.repositories import sync_data as db
from datetime import date

print("=" * 60)
print("测试 1：拉取 ETF 快照")
print("=" * 60)
etf_rows = sina.fetch_etf_snapshot()
print(f"✅ 拉取到 {len(etf_rows)} 只 ETF")
if etf_rows:
    print(f"\n前3只 ETF:")
    for row in etf_rows[:3]:
        print(f"  {row['code']} {row['name']}: {row['close']}")

print("\n" + "=" * 60)
print("测试 2：写入数据库")
print("=" * 60)
trade_date = date.today().isoformat()
n = db.save_snapshot(trade_date, etf_rows[:5])  # 只写前5只测试
print(f"✅ 已写入 {n} 条 ETF 快照")

print("\n" + "=" * 60)
print("测试 3：查询验证")
print("=" * 60)
test_code = etf_rows[0]['code']
print(f"查询 {test_code} 的最新行情:")
latest = db.get_latest_rows()
etf_in_db = [r for r in latest if r['code'] == test_code]
if etf_in_db:
    print(f"  ✅ 找到: {etf_in_db[0]['code']} {etf_in_db[0]['name']} {etf_in_db[0]['close']}")
else:
    print(f"  ❌ 未找到（可能被其他日期的记录覆盖）")

print("\n完成测试")
