import requests
import json

# 模拟前端筛选请求：只勾选"板块行情"，选择"房地产业"（行业板块）
body = {
    "strategies": [],
    "conditions": [],
    "sector": {
        "enabled": True,
        "mode": "manual",
        "names": ["房地产业"]  # 行业板块
    },
    "limit": 300
}

r = requests.post("http://localhost:8088/api/screen", json=body)
print(f"状态码: {r.status_code}")
result = r.json()
print(f"返回股票数: {len(result.get('items', []))}")
print(f"错误信息: {result.get('error')}")
if result.get('items'):
    print(f"前3只: {[s['name'] for s in result['items'][:3]]}")

# 对比：选择"大健康"（概念板块）
body2 = {
    "strategies": [],
    "conditions": [],
    "sector": {
        "enabled": True,
        "mode": "manual",
        "names": ["大健康"]  # 概念板块
    },
    "limit": 300
}

r2 = requests.post("http://localhost:8088/api/screen", json=body2)
print(f"\n概念板块测试:")
print(f"状态码: {r2.status_code}")
result2 = r2.json()
print(f"返回股票数: {len(result2.get('items', []))}")
if result2.get('items'):
    print(f"前3只: {[s['name'] for s in result2['items'][:3]]}")
