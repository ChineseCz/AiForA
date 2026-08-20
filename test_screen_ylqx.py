import requests

r = requests.post('http://localhost:8088/api/user/guest-login')
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

body = {
    "strategies": [],
    "conditions": [],
    "sector": {
        "enabled": True,
        "mode": "manual",
        "names": ["医疗器械"],  # 去掉后缀
        "days": 7,
        "user_ids": []
    },
    "limit": 300
}

print("请求体:", body)
r2 = requests.post('http://localhost:8088/api/screen', headers=headers, json=body)
print(f"状态码: {r2.status_code}")
result = r2.json()
count = len(result.get('items', []))
print(f"返回结果数: {count}")
if count == 0:
    print(f"完整响应: {result}")
