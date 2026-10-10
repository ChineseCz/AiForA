"""导出微信公众号文章访问会话，供服务器 browser-worker 使用。

用法：
    cd backend
    python export_wechat_state.py

完成微信验证后，data/wechat-state.json 会被本地 Docker 的
browser-worker 读取；重启本地容器即可。
"""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PROFILE_DIR = os.path.join(DATA_DIR, "wechat_edge_profile")
STATE_FILE = os.path.join(DATA_DIR, "wechat-state.json")
ARTICLE_URL = "https://mp.weixin.qq.com/s/feSy-YK_KiOMWI6pj1Kx2Q"


def main():
    from playwright.sync_api import sync_playwright

    print("正在打开 Edge，请在窗口中完成微信环境验证。")
    print("脚本会自动等待文章正文出现，检测成功后自动保存会话。\n")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            channel="msedge",
            headless=False,
            locale="zh-CN",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.goto(ARTICLE_URL, wait_until="domcontentloaded", timeout=60000)
        article_page = None
        deadline = time.time() + 180
        while time.time() < deadline:
            for candidate in ctx.pages:
                try:
                    if candidate.locator("#js_content").count() > 0:
                        article_page = candidate
                        break
                except Exception:
                    continue
            if article_page:
                break
            print("等待微信验证完成...", flush=True)
            time.sleep(2)
        if article_page is None:
            print("等待超时，未检测到文章正文，不保存无效会话。")
            ctx.close()
            return
        os.makedirs(DATA_DIR, exist_ok=True)
        ctx.storage_state(path=STATE_FILE)
        ctx.close()
    print(f"会话已保存：{STATE_FILE}")
    print("本地 Docker 下一步：")
    print("  cd backend")
    print("  docker compose restart browser-worker")


if __name__ == "__main__":
    main()
