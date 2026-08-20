from fastapi.testclient import TestClient
from app.main import create_app
from app.core.security import create_access_token

app = create_app()
client = TestClient(app)

# 生成测试 token
token = create_access_token("1123093545@qq.com", typ="visitor", sty="email")
print("Generated token:", token[:50] + "...")

# 测试 /me 端点
response = client.get("/api/user/me", headers={"Authorization": f"Bearer {token}"})
print("Status:", response.status_code)
print("Body:", response.text)
