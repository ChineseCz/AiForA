import sys
sys.path.insert(0, '/app')

from app.services import screen_api

# 模拟前端请求：只勾选板块筛选，选择"房地产业"
body = {
    "strategies": [],
    "conditions": [],
    "sector": {
        "enabled": True,
        "mode": "manual",
        "names": ["房地产业"]
    },
    "limit": 300
}

result, status = screen_api.screen(body)
print(f"状态码: {status}")
print(f"返回股票数: {len(result.get('items', []))}")
print(f"错误信息: {result.get('error')}")
if result.get('items'):
    print(f"前3只: {[(r['code'], r['name']) for r in result['items'][:3]]}")

# 对比概念板块
body2 = {
    "strategies": [],
    "conditions": [],
    "sector": {
        "enabled": True,
        "mode": "manual",
        "names": ["大健康"]
    },
    "limit": 300
}

result2, status2 = screen_api.screen(body2)
print(f"\n概念板块:")
print(f"状态码: {status2}")
print(f"返回股票数: {len(result2.get('items', []))}")
if result2.get('items'):
    print(f"前3只: {[(r['code'], r['name']) for r in result2['items'][:3]]}")
