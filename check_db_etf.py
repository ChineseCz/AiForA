"""检查数据库中 ETF 数量和目标代码"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.repositories import sync_data as db

rows = db.get_latest_rows()
rows_dict = {r['code']: r for r in rows}

target_codes = ['513310', '517520', '161226', '513090', '159206', '562500']

print("检查目标代码是否在数据库:")
for code in target_codes:
    if code in rows_dict:
        r = rows_dict[code]
        print(f"✅ {code} {r['name']}")
    else:
        print(f"❌ {code} 不在数据库")

print(f"\n数据库按前缀统计:")
prefixes = {}
for r in rows:
    prefix = r['code'][:2]
    prefixes[prefix] = prefixes.get(prefix, 0) + 1

for prefix in sorted(prefixes.keys()):
    print(f"  {prefix}开头: {prefixes[prefix]} 条")

print(f"\n总记录: {len(rows)} 条")
