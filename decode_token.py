import sys
import base64
import json

# 从命令行读取 token
if len(sys.argv) < 2:
    print("Usage: python decode_token.py <your_jwt_token>")
    sys.exit(1)

token = sys.argv[1]
parts = token.split('.')

if len(parts) != 3:
    print("Invalid JWT format")
    sys.exit(1)

# 解码 payload (第二部分)
payload_b64 = parts[1]
# 补齐 padding
payload_b64 += '=' * (4 - len(payload_b64) % 4)
payload_json = base64.urlsafe_b64decode(payload_b64)
payload = json.loads(payload_json)

print(json.dumps(payload, indent=2, ensure_ascii=False))
