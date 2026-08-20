import requests

r = requests.post('http://localhost:8088/api/user/guest-login')
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

r2 = requests.get('http://localhost:8088/api/sectors/rank', headers=headers)
data = r2.json()

print(f'返回类型: {type(data)}')
if isinstance(data, dict):
    print(f'返回字段: {list(data.keys())}')
    print(f'返回内容: {data}')
    items = data.get('items', [])
else:
    items = data if isinstance(data, list) else []

print(f'板块排行榜数量: {len(items)}')

semi = [s for s in items if '半导体' in s.get('sector', '')]
print(f'\n包含半导体的板块:')
for s in semi[:5]:
    print(f"  {s['sector']:20s} 成分股:{s.get('member_count', 0):3d} 涨:{s.get('up_count', 0):2d}")

med = [s for s in items if '医疗' in s.get('sector', '')]
print(f'\n包含医疗的板块:')
for s in med[:10]:
    print(f"  {s['sector']:20s} 成分股:{s.get('member_count', 0):3d} 涨:{s.get('up_count', 0):2d}")
