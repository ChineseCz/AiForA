import sys
sys.path.insert(0, 'backend')
from app.repositories import sync_data as db

# 查找数据库中的 ETF（51/15/56 开头）
all_stocks = db.get_latest_rows()
etfs = [r for r in all_stocks if r['code'].startswith(('51', '15', '56'))]

print(f'数据库中共有 {len(all_stocks)} 只股票')
print(f'其中 ETF 数量: {len(etfs)}')
if etfs:
    print('\n前10个 ETF:')
    for etf in etfs[:10]:
        print(f'  {etf["code"]} - {etf["name"]}')
else:
    print('\n数据库中没有 ETF 记录')
