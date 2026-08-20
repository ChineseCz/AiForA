import requests

# 获取游客 token
r = requests.post("http://localhost:8088/api/user/guest-login")
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 测试几个可能有问题的行业
test_sectors = ["半导体", "医疗机械", "房地产业", "大健康"]

for sector in test_sectors:
    body = {
        "strategies": [],
        "conditions": [],
        "sector": {
            "enabled": True,
            "mode": "manual",
            "names": [sector],
            "days": 7,
            "user_ids": []
        },
        "limit": 300
    }
    r = requests.post("http://localhost:8088/api/screen", headers=headers, json=body)
    result = r.json()
    count = len(result.get('items', []))
    print(f"{sector:12s} -> {count:3d} 只")
    if count == 0:
        # 检查这个板块是否在板块名录里
        r2 = requests.get("http://localhost:8088/api/sectors", headers=headers)
        sectors_data = r2.json()
        sector_list = sectors_data if isinstance(sectors_data, list) else sectors_data.get('items', [])
        matched = [s for s in sector_list if s.get('name') == sector]
        if matched:
            print(f"  ✓ 板块存在：{matched[0]}")
            # 检查成分股
            r3 = requests.get(f"http://localhost:8088/api/sectors/{matched[0]['board_code']}/members", headers=headers)
            members = r3.json()
            print(f"  成分股接口返回：{len(members)} 只")
        else:
            print(f"  ✗ 板块不存在于 sector_catalog")
