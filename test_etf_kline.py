"""测试 ETF K线回补（Playwright 真实浏览器）"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import json
from playwright.sync_api import sync_playwright

# 测试代码
test_etfs = [
    ('510300', '沪深300ETF'),
    ('510500', '中证500ETF'),
    ('159915', '创业板ETF'),
    ('512880', '证券ETF'),
    ('515050', '5G ETF'),
]

def sina_symbol(code: str) -> str:
    """转新浪代码格式"""
    if code.startswith('51') or code.startswith('56'):
        return f'sh{code}'
    elif code.startswith('15'):
        return f'sz{code}'
    elif code.startswith('6') or code.startswith('9'):
        return f'sh{code}'
    else:
        return f'sz{code}'

def browser_fetch_json(page, url: str):
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

print('🚀 测试 ETF K线回补（Playwright + Edge）\n')

with sync_playwright() as p:
    # 使用 Edge
    ctx = p.chromium.launch_persistent_context(
        user_data_dir='data/edge_profile_test',
        channel='msedge',
        headless=False,
        locale='zh-CN',
        viewport=None,
        args=['--disable-blink-features=AutomationControlled'],
    )
    page = ctx.new_page()

    try:
        # 先导航到新浪页面，建立同源上下文
        print('📍 导航到新浪行情页...')
        page.goto('https://quotes.sina.cn/', wait_until='domcontentloaded')
        page.wait_for_timeout(2000)
        print('✅ 导航完成\n')

        for code, name in test_etfs:
            symbol = sina_symbol(code)
            url = f'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=10'

            status, text = browser_fetch_json(page, url)
            text = text.strip()

            if status == 200 and text.startswith('['):
                try:
                    items = json.loads(text)
                    print(f'✅ {code} ({name}): 成功返回 {len(items)} 条K线')
                    if items:
                        latest = items[-1]
                        print(f'   最新: {latest.get("day")} open={latest.get("open")} close={latest.get("close")} volume={latest.get("volume")}')
                except Exception as e:
                    print(f'❌ {code} ({name}): JSON解析失败 - {e}')
            else:
                print(f'❌ {code} ({name}): status={status}, text={text[:200]}')
            print()
    finally:
        ctx.close()

print('✅ 测试完成')
