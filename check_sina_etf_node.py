import requests
import json

r = requests.get(
    'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes',
    timeout=10
)
data = json.loads(r.content.decode('utf-8'))

# 打印顶级节点
print("顶级节点：")
for item in data[1]:
    print(f"  {item[0]}")

# 找 ETF 节点
for item in data[1]:
    if 'ETF' in item[0] or 'etf' in item[0] or '基金' in item[0]:
        print(f"\n找到节点: {item[0]}")
        print(f"节点结构: {item[:2]}")
        if len(item) > 1 and item[1]:
            print(f"子节点前3个:")
            for sub in item[1][:3]:
                print(f"  {sub}")
