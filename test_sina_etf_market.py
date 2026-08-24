import requests
import json
import re

# 测试 ETF 市场数据
COUNT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount"
DATA_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

# 1. 获取 ETF 总数
r = requests.get(COUNT_URL, params={"node": "etf_hq_fund"}, timeout=10)
print(f"ETF 总数响应: {r.text}")
total = int(re.findall(r"\d+", r.text)[0])
print(f"ETF 总数: {total}")

# 2. 获取第一页数据
r = requests.get(
    DATA_URL,
    params={
        "page": "1",
        "num": "80",
        "sort": "symbol",
        "asc": "1",
        "node": "etf_hq_fund",
        "symbol": "",
        "_s_r_a": "page",
    },
    timeout=10,
)
items = r.json()
print(f"\n第一页 ETF 数量: {len(items)}")

if items:
    print(f"\n前3个 ETF:")
    for item in items[:3]:
        print(f"  代码: {item.get('code')}, 名称: {item.get('name')}, 价格: {item.get('trade')}")

    print(f"\n第一个 ETF 完整字段:")
    print(json.dumps(items[0], ensure_ascii=False, indent=2))
