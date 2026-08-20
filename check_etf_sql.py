import sys
sys.path.insert(0, 'backend')
from app.core.sync_db import sync_session
from sqlalchemy import text

# 直接用 SQL 查询 ETF 数量
with sync_session() as session:
    result = session.execute(text("""
        SELECT code, name
        FROM stock_daily
        WHERE code LIKE '51%' OR code LIKE '15%' OR code LIKE '56%'
        LIMIT 10
    """))
    etfs = result.fetchall()

print(f'数据库中 ETF 数量: {len(etfs)}')
if etfs:
    print('\n找到的 ETF:')
    for code, name in etfs:
        print(f'  {code} - {name}')
else:
    print('\n数据库中没有 ETF 记录')
    print('新浪行情同步接口返回的是 A 股，不包含 ETF')
    print('如果需要 ETF K线回补，需要先手动添加 ETF 到 stock_daily 表')
