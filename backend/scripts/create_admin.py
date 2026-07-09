"""手动创建/重置管理员账号。

用法：
    python -m scripts.create_admin --username admin --password 'yourStrongPass'
"""
import argparse
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.core.security import hash_password  # noqa: E402
from app.repositories import admins as admins_repo  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    args = ap.parse_args()

    created = admins_repo.create_admin(args.username, hash_password(args.password))
    if created:
        print(f"✅ 管理员已创建：{args.username}（id={created}）")
    else:
        print(f"⚠️ 用户名已存在：{args.username}（如需改密码请先删除旧号或另加改密逻辑）")


if __name__ == "__main__":
    main()
