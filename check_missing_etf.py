"""检查指定 ETF 是否在数据库中"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.repositories import sync_data as db

# 去掉交易所前缀
codes = ['513310', '517520', '161226', '513090', '159206', '562500']
rows = db.get_latest_rows()
rows_dict = {r['code']: r for r in rows}

print('检查这些代码是否在数据库中:')
for code in codes:
    if code in rows_dict:
        r = rows_dict[code]
        print(f'✅ {code} {r["name"]}: 存在')
    else:
        print(f'❌ {code}: 不在数据库中')

print(f'\n数据库总记录: {len(rows)} 条')
print(f'51开头: {sum(1 for r in rows if r["code"].startswith("51"))} 条')
print(f'15开头: {sum(1 for r in rows if r["code"].startswith("15"))} 条')
print(f'16开头: {sum(1 for r in rows if r["code"].startswith("16"))} 条')
print(f'56开头: {sum(1 for r in rows if r["code"].startswith("56"))} 条')
print(f'50开头: {sum(1 for r in rows if r["code"].startswith("50"))} 条')
