"""测试 ETF K线回补完整流程"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'backend')

from app.scrapers.kline import _fetch_and_save_bars
from app.repositories import sync_data as db

# 测试 ETF 代码
test_codes = ['510300', '159915', '512880']

print('🚀 测试 ETF K线回补（单股测试）\n')
print('先检查数据库中是否有这些 ETF...\n')

for code in test_codes:
    row = db.get_latest_by_code(code)
    if row:
        print(f'✅ {code} 已存在数据库: {row["name"]}')
    else:
        print(f'⚠️  {code} 不在数据库中')
print()

print('现在测试 K 线拉取和保存...\n')

for code in test_codes:
    print(f'📊 测试 {code}...')
    try:
        result = _fetch_and_save_bars(code, days=30, browser_channel='msedge')
        print(f'✅ {code}: 成功保存 {result} 条K线')
    except Exception as e:
        print(f'❌ {code}: {e}')
        import traceback
        traceback.print_exc()
    print()

print('✅ 测试完成')
