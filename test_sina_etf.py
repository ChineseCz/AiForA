"""测试新浪 ETF 接口是否包含指定代码"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.services.external import sina

print("正在拉取新浪 ETF 快照...")
etfs = sina.fetch_etf_snapshot()
print(f"总共拉到 {len(etfs)} 只 ETF")

# 检查指定代码
target_codes = ['513310', '517520', '161226', '513090', '159206', '562500']
etf_dict = {e['code']: e for e in etfs}

print("\n检查目标代码:")
for code in target_codes:
    if code in etf_dict:
        print(f"✅ {code} {etf_dict[code]['name']}")
    else:
        print(f"❌ {code} 不在新浪 etf_hq_fund 节点中")

# 统计前缀分布
print("\n按前缀统计:")
prefixes = {}
for e in etfs:
    prefix = e['code'][:2]
    prefixes[prefix] = prefixes.get(prefix, 0) + 1

for prefix in sorted(prefixes.keys()):
    print(f"  {prefix}开头: {prefixes[prefix]} 只")
