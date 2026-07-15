"""
雪球交易记录 API 探测脚本
运行方式：python scripts/discover_trade_api.py
脚本启动后请在打开的浏览器里手动点击雪球的「买卖记录」/「成交记录」页面，
脚本会把捕获到的可疑 API 响应打印出来，帮助定位接口 URL。
"""
import asyncio
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "edge_profile")
TRADE_KEYWORDS = ["trade", "order", "deal", "entrust", "成交", "委托", "持仓", "portfolio", "position"]


async def main():
    from playwright.async_api import async_playwright

    print("启动 Edge，请在浏览器里手动导航到雪球交易记录页面...")
    print("脚本会监听 60 秒内的 API 响应，按 Ctrl+C 提前结束\n")

    captured = []

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=os.path.abspath(PROFILE_DIR),
            channel="msedge",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        async def on_response(response):
            url = response.url
            lower_url = url.lower()
            if not any(kw in lower_url for kw in TRADE_KEYWORDS):
                return
            # 只看 JSON API
            ct = response.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                body = await response.json()
                entry = {"url": url, "status": response.status, "body": body}
                captured.append(entry)
                print(f"\n[捕获] {url}")
                print(json.dumps(body, ensure_ascii=False, indent=2)[:800])
                print("..." if len(json.dumps(body)) > 800 else "")
            except Exception:
                pass

        page.on("response", on_response)
        await page.goto("https://xueqiu.com", timeout=30000)

        print("浏览器已打开，请手动点击交易/买卖记录页面，等待 60 秒...")
        await asyncio.sleep(60)
        await browser.close()

    print(f"\n共捕获 {len(captured)} 条可疑 API 响应")
    if captured:
        out = os.path.join(os.path.dirname(__file__), "discovered_trade_apis.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)
        print(f"已保存到 {out}")


if __name__ == "__main__":
    asyncio.run(main())
