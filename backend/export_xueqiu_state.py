"""导出雪球登录态到 xueqiu-state.json（方案C：Storage State 容器化部署用）

用法（本机 Windows 执行）：
    cd backend
    python export_xueqiu_state.py

将 data/edge_profile/ 中的 Edge 登录态导出为 Playwright storage state 格式，
保存到 data/xueqiu-state.json，再上传到服务器即可让 Docker browser-worker 容器使用。

上传命令：
    scp data/xueqiu-state.json ubuntu@<服务器IP>:/data/app/backend/data/
    ssh ubuntu@<服务器IP> "cd /data/app/backend && docker compose restart browser-worker"
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PROFILE_DIR = os.path.join(DATA_DIR, "edge_profile")
STATE_FILE = os.path.join(DATA_DIR, "xueqiu-state.json")


def main():
    from playwright.sync_api import sync_playwright

    print("启动 Edge，读取 data/edge_profile/ 登录态...")
    print("如果还未登录雪球，请在弹出的浏览器窗口中手动登录，完成后回来按回车。")
    print()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="msedge",
            headless=False,
            locale="zh-CN",
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.goto("https://xueqiu.com", wait_until="domcontentloaded", timeout=30000)

        # 检查是否已登录（已登录页面有用户头像区域）
        try:
            page.wait_for_selector(".nav-user-info, .user-avatar, [class*='userInfo']", timeout=5000)
            print("✅ 检测到已登录状态")
        except Exception:
            print("⚠️  未检测到登录状态，请在浏览器窗口中手动登录雪球")
            input("登录完成后按回车继续...")

        os.makedirs(DATA_DIR, exist_ok=True)
        ctx.storage_state(path=STATE_FILE)
        ctx.close()

    print(f"✅ 登录态已导出到 {STATE_FILE}")
    print()
    print("下一步：上传到服务器")
    print(f"    scp {STATE_FILE} ubuntu@<服务器IP>:/data/app/backend/data/")
    print("    ssh ubuntu@<服务器IP> \"cd /data/app/backend && docker compose restart browser-worker\"")


if __name__ == "__main__":
    main()
