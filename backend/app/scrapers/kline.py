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
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);
            const r = await fetch(url, {credentials: 'include', signal: controller.signal});
            clearTimeout(timeoutId);
            return {status: r.status, text: await r.text()};
        } catch (e) { return {status: -1, text: String(e)}; }
    }"""
    result = page.evaluate(js, url)
    return result["status"], result["text"] or ""


def backfill_history(days: int = 60, delay: float = 0.5, batch_size: int = 10) -> tuple[int, int]:
    import random

    from playwright.sync_api import sync_playwright

    all_codes = [r["code"] for r in db.get_latest_rows() if r.get("code")]
    if not all_codes:
        print("⚠️ 还没有行情快照，请先运行行情同步")
        return 0, 0

    # 过滤：只回补有缺失的股票（60天约42个交易日，低于38天视为缺失）
    codes = [c for c in all_codes if db.has_missing_bars(c, days)]
    skipped = len(all_codes) - len(codes)
    print(f"📊 共 {len(all_codes)} 只股票，{skipped} 只数据完整跳过，{len(codes)} 只待回补")

    today = date.today().isoformat()
    total = len(codes)
    ok, fail = 0, 0
    if not codes:
        print("✅ 所有股票 K线数据完整，无需回补")
        return 0, 0

    with sync_playwright() as p:
        if settings.browser_channel:
            # 本机模式：Edge + persistent profile（K 线不需要登录态，只借浏览器指纹）
            profile_dir = os.path.join(settings.data_dir, "edge_profile_stock")
            os.makedirs(profile_dir, exist_ok=True)
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel=settings.browser_channel,
                headless=settings.headless,
                locale="zh-CN",
                viewport=None,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = ctx.new_page()
        else:
            # 服务器模式：Chromium 无头，新浪 K 线无需登录态，只需真实浏览器指纹绕反爬
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(locale="zh-CN")
            page = ctx.new_page()
        try:
            page.goto(_history_api_url(codes[0], days), wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            consec_fail = 0
            batch_buffer = []  # 累积 (code, bars) 元组
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
                        batch_buffer.append((code, bars))
                    ok += 1
                    consec_fail = 0
                else:
                    fail += 1
                    consec_fail += 1
                    if consec_fail >= 10:
                        print(f"⚠️ 连续 {consec_fail} 只失败，暂停60秒…")
                        time.sleep(60)
                        consec_fail = 0

                # 批次写入：每累积 batch_size 只或到达末尾时提交
                if len(batch_buffer) >= batch_size or i == total:
                    if batch_buffer:
                        db.save_history_bars_batch(batch_buffer)
                        batch_buffer = []

                if i % 50 == 0 or i == total:
                    print(f"… 已回补 {i}/{total} 只（成功{ok}/失败{fail}） …")
                time.sleep(random.uniform(delay * 0.6, delay * 1.4))
        finally:
            ctx.close()

    print(f"✅ 历史K线回补完成：成功 {ok} 只，失败 {fail} 只")
    return ok, fail
