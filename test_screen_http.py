import requests
import json

# 先获取游客 token
r = requests.post("http://localhost:8088/api/user/guest-login")
token = r.json()["access_token"]
print(f"游客 token: {token[:40]}...")

headers = {"Authorization": f"Bearer {token}"}

# 测试行业板块筛选
body1 = {
    "strategies": [],
    "conditions": [],
    "sector": {
        "enabled": True,
        "mode": "manual",
        "names": ["房地产业"],
        "days": 7,
        "user_ids": []
    },
    "limit": 300
}

print("\n=== 测试行业板块「房地产业」 ===")
r1 = requests.post("http://localhost:8088/api/screen", headers=headers, json=body1)
print(f"状态码: {r1.status_code}")
result1 = r1.json()
print(f"返回股票数: {len(result1.get('items', []))}")
print(f"错误信息: {result1.get('error')}")
if result1.get('items'):
    print(f"前3只: {[(s['code'], s['name']) for s in result1['items'][:3]]}")

# 测试概念板块筛选
body2 = {
    "strategies": [],
    "conditions": [],
    "sector": {
        "enabled": True,
        "mode": "manual",
        "names": ["大健康"],
        "days": 7,
        "user_ids": []
    },
    "limit": 300
}

print("\n=== 测试概念板块「大健康」 ===")
r2 = requests.post("http://localhost:8088/api/screen", headers=headers, json=body2)
print(f"状态码: {r2.status_code}")
result2 = r2.json()
print(f"返回股票数: {len(result2.get('items', []))}")
if result2.get('items'):
    print(f"前3只: {[(s['code'], s['name']) for s in result2['items'][:3]]}")
