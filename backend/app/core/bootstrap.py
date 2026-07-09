"""启动引导：admins 表为空且配置了 ADMIN_USERNAME/ADMIN_PASSWORD 时，自动建一个管理员。

幂等：已有任何管理员则跳过。生产建议改用 scripts/create_admin.py 手动建号，避免密码进 env。
"""
from app.core.config import settings
from app.core.security import hash_password
from app.repositories import admins as admins_repo


def bootstrap_admin() -> None:
    if not (settings.admin_username and settings.admin_password):
        return
    try:
        if admins_repo.count_admins() > 0:
            return
        created = admins_repo.create_admin(
            settings.admin_username, hash_password(settings.admin_password)
        )
        if created:
            print(f"✅ 已引导创建管理员：{settings.admin_username}")
    except Exception as e:  # noqa: BLE001 —— 引导失败不应阻断启动
        print(f"⚠️ 引导管理员失败：{e}")
