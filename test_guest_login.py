import requests
import json

# 先获取游客 token
r = requests.post("http://localhost:8088/api/user/login/guest")
print(f"游客登录响应: {r.status_code}")
print(f"响应内容: {r.text}")
