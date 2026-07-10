"""历史K线批量回补（宿主 worker 专用）：Playwright 驱动真实 Edge，页面内同源 fetch 绕反爬。

从旧 stock.py backfill_history 移植。playwright 延迟导入，仅宿主 worker 执行。
新浪该接口对纯 requests 反爬阈值极低（~250 只后 456 永久拒绝），真实浏览器指纹可连续 500+ 只 0 失败。
"""
import json
import os
import time
from datetime import date

from app.core.config import settings
from app.repositories import sync_data as db
from app.services.adjust import compute_qfq
from app.services.external.sina import fetch_qfq_factors, sina_symbol

_SINA_HIST_URL = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _history_api_url(code: str, days: int) -> str:
    return f"{_SINA_HIST_URL}?symbol={sina_symbol(code)}&scale=240&ma=no&datalen={days}"


def _browser_fetch_json(page, url: str) -> tuple[int, str]:
    js = """async (url) => {
        try {
            const r = await fetch(url, {credentials: 'include'});
            return {status: r.status, text: await r.text()};
        } catch (e) { return {status: -1, text: String(e)}; }
    }"""
    result = page.evaluate(js, url)
    return result["status"], result["text"] or ""


def backfill_history(days: int = 60, delay: float = 0.5) -> tuple[int, int]:
    import random

    from playwright.sync_api import sync_playwright

    codes = [r["code"] for r in db.get_latest_rows() if r.get("code")]
    today = date.today().isoformat()
    total = len(codes)
    ok, fail = 0, 0
    if not codes:
        print("⚠️ 还没有行情快照，请先运行行情同步")
        return 0, 0

    profile_dir = os.path.join(settings.data_dir, "edge_profile_stock")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel="msedge",
            headless=settings.headless,
            locale="zh-CN",
            viewport=None,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = ctx.new_page()
            page.goto(_history_api_url(codes[0], days), wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            consec_fail = 0
            for i, code in enumerate(codes, 1):
                status, text = _browser_fetch_json(page, _history_api_url(code, days))
                text = text.strip()
                if status == 200 and text.startswith("["):
                    try:
                        items = json.loads(text)
                    except ValueError:
                        items = []
                    bars = []
                    for it in items:
                        day = it.get("day")
                        if not day or day >= today:
                            continue
                        bars.append({
                            "trade_date": day, "code": code,
                            "open": _to_float(it.get("open")), "close": _to_float(it.get("close")),
                            "high": _to_float(it.get("high")), "low": _to_float(it.get("low")),
                            "volume": _to_float(it.get("volume")),
                        })
                    if bars:
                        # 新浪K线接口本身给的是不复权价，除权除息当天会有断崖式跳空——
                        # 拿这只股票的复权因子表（纯 requests，不用走上面这套浏览器反爬）转成前复权再存。
                        # 因子表拉不到（没有除权记录/接口偶发失败）就原样存，不阻塞整个回补流程。
                        try:
                            factors = fetch_qfq_factors(code)
                        except Exception as e:  # noqa: BLE001
                            print(f"⚠️ 复权因子拉取异常 {code}：{e}")
                            factors = []
                        bars = compute_qfq(bars, factors)
                        db.save_history_bars(bars)
                    ok += 1
                    consec_fail = 0
                else:
                    fail += 1
                    consec_fail += 1
                    if consec_fail >= 10:
                        print(f"⚠️ 连续 {consec_fail} 只失败，暂停60秒…")
                        time.sleep(60)
                        consec_fail = 0
                if i % 50 == 0 or i == total:
                    print(f"… 已回补 {i}/{total} 只（成功{ok}/失败{fail}） …")
                time.sleep(random.uniform(delay * 0.6, delay * 1.4))
        finally:
            ctx.close()

    print(f"✅ 历史K线回补完成：成功 {ok} 只，失败 {fail} 只")
    return ok, fail
