import requests

r = requests.post('http://localhost:8088/api/user/guest-login')
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}
r2 = requests.get('http://localhost:8088/api/screen/sectors', headers=headers)
sectors = r2.json()

# 搜索包含'半导体'的板块
semi = [s for s in sectors if '半导体' in s.get('name', '')]
print(f'包含半导体的板块：{len(semi)} 个')
for s in semi[:10]:
    print(f'  {s["name"]:30s} {s["board_code"]:15s} {s["kind"]}')

# 搜索包含'医疗'的板块
med = [s for s in sectors if '医疗' in s.get('name', '')]
print(f'\n包含医疗的板块：{len(med)} 个')
for s in med[:10]:
    print(f'  {s["name"]:30s} {s["board_code"]:15s} {s["kind"]}')

# 统计来源
from collections import Counter
sources = Counter(s['board_code'].split('_')[0] for s in sectors)
print(f'\n板块来源统计：')
for src, cnt in sources.items():
    print(f'  {src:6s} {cnt:4d} 个')
