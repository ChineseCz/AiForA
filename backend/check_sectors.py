import requests

r = requests.get('http://localhost:8088/api/screen/sectors')
data = r.json()

print(f"返回类型: {type(data)}")
if isinstance(data, dict):
    print(f"返回字段: {list(data.keys())}")
    sectors = data.get('sectors') or data.get('data') or []
else:
    sectors = data

print(f"\n板块总数: {len(sectors)}")
print("\n医疗相关板块：")
for s in sectors:
    if '医疗' in s['name']:
        print(f"  {s['name']} ({s['board_code']})")

print("\n半导体相关板块：")
for s in sectors:
    if '半导体' in s['name']:
        print(f"  {s['name']} ({s['board_code']})")
