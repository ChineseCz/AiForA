"""雪球抓取（宿主 worker 专用）：Playwright 驱动真实 Edge + 持久化登录态。

从旧 scraper.py 忠实移植，两处适配：
1. playwright 改为函数内延迟导入 —— 让本模块可在无 playwright 的容器里被 import（Celery 注册任务需要），
   只有真正执行抓取时才要求 playwright（仅宿主 worker 装）。
2. 配置读 settings；采集名单读 xueqiu_users 表（get_enabled_xueqiu_users），取代旧 .env 的 XUEQIU_USERS。

只应由消费 QUEUE_BROWSER 的 Windows 宿主 worker 执行。
"""
import json
import os
import random
import re
import time
from datetime import datetime

from app.core.config import settings
from app.repositories import sync_data as db

HOME = "https://xueqiu.com"

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || {runtime: {}};
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""


def _profile_dir() -> str:
    return settings.profile_dir or os.path.join(settings.data_dir, "edge_profile")


def clean_text(html: str) -> str:
    from bs4 import BeautifulSoup
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return normalize_post_text(text)


# 专栏类帖子源 HTML 里每个块级元素（<p>/<li>/<div>）都会被 get_text("\n") 拆成独立一行，
# 造成"编号"、"标题词+冒号"、"内容"本该在同一行的东西被空行隔断，如：
# "1.\n\n福新转债\n\n：不强赎。" —— 下面几条规则把这类"本该是一行"的相邻片段重新粘回去，
# 真正的段落间空行（两句完整陈述之间）不受影响。
_NUM_MARKER_RE = re.compile(r"^(?:\d{1,3}[.．、)）]|[①-⑳]|\([0-9]{1,3}\))$")
_LEADING_PUNCT_RE = re.compile(r"^[：:，,。.、）)]")


def normalize_post_text(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    merged: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # 独占一行的编号（"1." "①" "(1)"）后面紧跟的内容行合并到同一行
        if _NUM_MARKER_RE.match(stripped):
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            if j < n:
                merged.append(f"{stripped}{lines[j].strip()}")
                i = j + 1
                continue
        # 下一非空行以标点开头（"：不强赎。"）——是上一行的续接，不是新段落
        if merged:
            j = i
            while j < n and not lines[j].strip():
                j += 1
            if j < n and _LEADING_PUNCT_RE.match(lines[j].strip()):
                merged[-1] = f"{merged[-1]}{lines[j].strip()}"
                i = j + 1
                continue
        merged.append(stripped)
        i += 1
    return "\n\n".join(merged)


def ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


def _rand_secs(base: float | None = None, spread: float = 1.6) -> float:
    base = settings.request_delay if base is None else base
    return random.uniform(base, base * spread)


def _human_wait(page) -> None:
    page.wait_for_timeout(int(_rand_secs() * 1000))


def _human_sleep(base: float | None = None) -> None:
    time.sleep(_rand_secs(base))


def normalize_profile_url(user: str) -> str:
    user = user.strip()
    if user.startswith("http"):
        return user
    if user.isdigit():
        return f"{HOME}/u/{user}"
    return f"{HOME}/{user.lstrip('/')}"


def _is_truncated(status: dict) -> bool:
    raw = status.get("text", "") or ""
    if not raw.strip():
        return True
    return bool(status.get("truncated")) or "查看全文" in raw


def extract_images(status: dict) -> list[str]:
    pic = (status.get("pic") or "").split("!", 1)[0]
    infos = status.get("image_info_list") or []
    if not infos:
        return [pic] if pic else []
    if "/" not in pic:
        return [pic] if pic else []
    host_prefix = pic.rsplit("/", 1)[0]
    urls = []
    seen = set()
    for info in infos:
        fname = info.get("filename")
        if not fname or fname in seen:
            continue
        seen.add(fname)
        urls.append(f"{host_prefix}/{fname}")
    return urls or ([pic] if pic else [])


def open_context(playwright, headless: bool | None = None):
    _headless = settings.headless if headless is None else headless

    if settings.browser_channel:
        # 本机模式：Edge + persistent profile 目录，登录态自动持久
        profile = _profile_dir()
        os.makedirs(profile, exist_ok=True)
        ctx = playwright.chromium.launch_persistent_context(
            user_data_dir=profile,
            channel=settings.browser_channel,
            headless=_headless,
            locale="zh-CN",
            viewport=None,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
    else:
        # 服务器模式：Chromium 无头 + storage state 文件（由本机导出后上传）
        state_file = os.path.join(settings.data_dir, "xueqiu-state.json")
        browser = playwright.chromium.launch(
            headless=_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            locale="zh-CN",
            storage_state=state_file if os.path.exists(state_file) else None,
        )

    ctx.add_init_script(STEALTH_JS)
    return ctx


def _wait_waf(page, label: str, max_s: int = 60) -> bool:
    warned = False
    for _ in range(max_s):
        content = page.content()
        if "aliyun_waf" not in content and "aliyun-slide" not in content:
            return True
        if "aliyun-slide" in content and not warned:
            print(f"   ⚠️  {label} 弹出滑块验证，请在浏览器窗口中手动拖动完成（等待中…）")
            warned = True
        page.wait_for_timeout(1000)
    return "aliyun_waf" not in page.content()


def fetch_full_text_in_page(page, status_id: str) -> str | None:
    js = """async (id) => {
        try {
            const r = await fetch('/statuses/show.json?id=' + id,
                {credentials: 'include', headers: {'Accept': 'application/json'}});
            const d = await r.json();
            return d.text || '';
        } catch (e) { return ''; }
    }"""
    try:
        html = page.evaluate(js, status_id)
        return clean_text(html) if html else None
    except Exception:
        return None


def fetch_timeline_in_page(page, user_id: str, pg: int) -> tuple[str | None, str]:
    js = """async ([uid, p]) => {
        try {
            const r = await fetch(
                '/v4/statuses/user_timeline.json?user_id=' + uid + '&page=' + p,
                {credentials: 'include', headers: {'Accept': 'application/json'}});
            return await r.text();
        } catch (e) { return ''; }
    }"""
    try:
        raw = page.evaluate(js, [user_id, pg])
    except Exception:
        return None, "error"
    if not raw:
        return None, "empty"
    if raw.lstrip().startswith("<"):
        return None, "blocked"
    return raw, "ok"


def _day_start_ms(d) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000)


def crawl_user(ctx, user: str, since=None, until=None) -> tuple[str, str, int, int, bool, list[str]]:
    since_ms = _day_start_ms(since) if since else None
    until_ms = _day_start_ms(until) + 86_400_000 if until else None

    bodies: list[str] = []
    page = ctx.new_page()
    page.set_default_timeout(30000)

    def on_response(resp):
        if "user_timeline.json" in resp.url and "json" in (resp.headers.get("content-type") or ""):
            try:
                bodies.append(resp.text())
            except Exception:
                pass

    page.on("response", on_response)

    page.goto(HOME, wait_until="domcontentloaded")
    _wait_waf(page, "首页")

    page.goto(normalize_profile_url(user), wait_until="domcontentloaded")
    _wait_waf(page, f"主页 {user}")

    for _ in range(15):
        page.wait_for_timeout(1000)
        if bodies:
            break

    statuses: dict[str, dict] = {}

    def absorb(raw: str) -> tuple[int, int | None]:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return 0, None
        added = 0
        page_min = None
        for st in data.get("statuses", []):
            sid = st.get("id")
            created = int(st.get("created_at") or 0)
            if created and (page_min is None or created < page_min):
                page_min = created
            if sid is not None and str(sid) not in statuses:
                statuses[str(sid)] = st
                added += 1
        return added, page_min

    for raw in bodies:
        absorb(raw)

    uid = ""
    for st in statuses.values():
        uid = str((st.get("user") or {}).get("id") or "")
        if uid:
            break

    has_range = since_ms is not None or until_ms is not None
    page_cap = 2000 if has_range else settings.max_pages

    blocked = 0
    stopped_by_block = False

    if uid:
        pg = 2
        while pg <= page_cap:
            raw, status = fetch_timeline_in_page(page, uid, pg)
            if status == "blocked":
                blocked += 1
                try:
                    page.goto(HOME, wait_until="domcontentloaded")
                    _wait_waf(page, "重新预热")
                except Exception:
                    pass
                _human_wait(page)
                raw, status = fetch_timeline_in_page(page, uid, pg)
                if status == "blocked":
                    blocked += 1
                    stopped_by_block = True
                    break
            if status != "ok" or raw is None:
                break
            added, page_min = absorb(raw)
            if added == 0:
                break
            if since_ms is not None and page_min is not None and page_min < since_ms:
                break
            _human_wait(page)
            if pg % 8 == 0:
                _human_wait(page)
                _human_wait(page)
            pg += 1

    user_id = ""
    user_name = ""
    new_count = 0
    pending_brief_ids: list[str] = []
    for sid, st in statuses.items():
        uinfo = st.get("user") or {}
        user_id = str(uinfo.get("id") or user_id)
        user_name = uinfo.get("screen_name") or user_name

        created = int(st.get("created_at") or 0)
        if since_ms is not None and created < since_ms:
            continue
        if until_ms is not None and created >= until_ms:
            continue
        if db.post_exists(sid):
            continue

        text = clean_text(st.get("text", ""))
        if settings.fetch_full_text and _is_truncated(st):
            full = fetch_full_text_in_page(page, sid)
            if full and len(full) > len(text):
                text = full
            _human_wait(page)

        db.upsert_post({
            "id": sid, "user_id": user_id, "user_name": user_name, "created_at": created,
            "date": ms_to_date(created) if created else "",
            "text": text, "title": st.get("title") or "",
            "url": f"{HOME}{st.get('target', '')}",
            "like_count": int(st.get("like_count") or 0),
            "retweet_count": int(st.get("retweet_count") or 0),
            "reply_count": int(st.get("reply_count") or 0),
            "fav_count": int(st.get("fav_count") or 0),
            "raw_json": "",
            "images": json.dumps(extract_images(st), ensure_ascii=False),
            "fetched_at": int(time.time()),
        })
        new_count += 1
        if len(text) > settings.post_brief_min_length:
            pending_brief_ids.append(sid)

    try:
        page.close()
    except Exception:
        pass
    return user_id, user_name, new_count, blocked, stopped_by_block, pending_brief_ids


def crawl_all(since=None, until=None) -> tuple[dict[str, tuple[str, int]], list[str]]:
    """返回 ({user_id: (user_name, 本次新增条数)}, pending_brief_ids)。

    第一项仅含新增>0的大V——供调用方决定"谁需要重新生成当天总结"，避免没有新帖子也无脑重跑一遍 LLM。
    第二项是本次新增里正文超长、需要派发"一句话总结"LLM任务的帖子id列表。
    """
    from playwright.sync_api import sync_playwright

    users = db.get_enabled_xueqiu_users()
    if not users:
        print("⚠️  xueqiu_users 表里没有启用的大V，无可抓取对象。")
        return {}, []
    if since or until:
        print(f"📅 只抓时间段：{since or '最早'} ~ {until or '至今'}")
    print("🚀 启动浏览器，开始采集…")
    total_blocked = 0
    updated: dict[str, tuple[str, int]] = {}
    pending_brief_ids: list[str] = []
    with sync_playwright() as p:
        ctx = open_context(p)
        try:
            for i, user in enumerate(users):
                if i > 0:
                    _human_sleep(8.0)
                print(f"→ 正在抓取 {user} …")
                try:
                    uid, uname, n, blocked, stopped, brief_ids = crawl_user(ctx, user, since, until)
                    total_blocked += blocked
                    if n > 0 and uid:
                        updated[uid] = (uname, n)
                    pending_brief_ids.extend(brief_ids)
                    msg = f"✅ {uname or uid}（{uid}）：新增 {n} 条"
                    if blocked:
                        msg += f"；⚠️ 被 WAF 拦截 {blocked} 次"
                        if stopped:
                            msg += "，并因此提前停止（建议稍后重跑补齐）"
                    print(msg)
                except Exception as e:  # noqa: BLE001
                    print(f"❌ 抓取失败 {user}：{e}")
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    if total_blocked:
        print(f"\n⚠️  本次共有 {total_blocked} 次请求被 WAF 拦截，过几分钟重跑可补齐。")
    return updated, pending_brief_ids


def _xq_code_to_plain(code: str) -> str:
    """雪球代码带交易所前缀（SH600745/SZ000001/BJ430047）→ 项目统一用的纯6位数字（与 stock_daily.code 对齐）。"""
    return re.sub(r"^(SH|SZ|BJ)", "", code.strip().upper())


def fetch_industries(page) -> list[dict]:
    """134个申万行业名录（一/二/三级混合），需登录态，走已打开的页面内 fetch。"""
    js = """async () => {
        try {
            const r = await fetch('https://stock.xueqiu.com/v5/stock/screener/industries.json?category=cn',
                {credentials: 'include'});
            return await r.text();
        } catch (e) { return ''; }
    }"""
    raw = page.evaluate(js)
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [
        {"board_code": f"xq_{it['encode']}", "name": it["name"], "kind": "industry"}
        for it in data.get("data", {}).get("industries", []) if it.get("encode") and it.get("name")
    ]


_XQ_CODE_RE = re.compile(r"^(?:SH|SZ|BJ)\d{6}$")


def scrape_industry_members(page, ind_code: str, ind_name: str, max_pages: int = 40) -> list[str]:
    """打开某个申万行业详情页，切到每页90条，翻页读表格里的股票代码直到"下一页"变禁用。

    雪球该页面没有独立的成分股JSON接口（DOM渲染），只能像抓帖子一样过真实浏览器读页面内容。
    """
    from urllib.parse import quote

    url = f"{HOME}/hq/detail?market=CN&first_name=0&second_name=2&indCode={ind_code}&indName={quote(ind_name)}"
    page.goto(url, wait_until="domcontentloaded")
    if not _wait_waf(page, f"行业 {ind_name}"):
        return []

    # 等待表格容器出现（雪球用 React，DOM 要等 JS 挂载）
    try:
        page.wait_for_selector("table", timeout=5000)
    except Exception:
        return []

    def read_codes() -> list[str]:
        # 优化：只扫描 table 内的文本节点，避免全文档遍历
        raw = page.eval_on_selector_all(
            "table *",
            """els => {
                const re = /^(SH|SZ|BJ)\\d{6}$/;
                const out = [];
                for (const e of els) {
                    if (e.children.length === 0) {
                        const t = (e.innerText||'').trim();
                        if (re.test(t)) out.push(t);
                    }
                }
                return [...new Set(out)];
            }""",
        )
        return [c for c in raw if _XQ_CODE_RE.match(c)]

    try:
        page.click("text=90", timeout=3000)
        page.wait_for_load_state("networkidle", timeout=3000)
    except Exception:
        pass  # 成分股不足一页时可能没有"90"选项，用默认页大小也行

    seen: set[str] = set(read_codes())
    for _ in range(max_pages):
        btn = page.locator("text=下一页").first
        try:
            if "disabled" in (btn.get_attribute("outerHTML") or ""):
                break
            btn.click(timeout=3000)
            page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            break
        new_codes = set(read_codes()) - seen
        if not new_codes:
            break
        seen |= new_codes
    return [_xq_code_to_plain(c) for c in seen]


def sync_xueqiu_sectors() -> list[dict]:
    """全量同步雪球134个申万行业 + 各自成分股（宿主 browser 队列专用，需登录态）。

    返回 [{"board_code": "xq_S2701", "name": "半导体", "kind": "industry", "codes": [...]}, ...]；
    单个行业抓取失败跳过并继续（per-item 容错）。调用方负责写库，本函数只管抓取。
    """
    from playwright.sync_api import sync_playwright

    result: list[dict] = []
    with sync_playwright() as p:
        ctx = open_context(p)
        try:
            page = ctx.new_page()
            page.set_default_timeout(30000)
            page.goto(HOME + "/hq/industry", wait_until="domcontentloaded")
            _wait_waf(page, "行业板块")
            page.wait_for_timeout(1500)

            industries = fetch_industries(page)
            if not industries:
                print("⚠️ 雪球行业名录拉取失败（可能登录态失效，需重新 login）")
                return []
            print(f"📋 雪球行业名录：{len(industries)} 个，开始逐个抓成分股…")

            for i, ind in enumerate(industries, 1):
                ind_code = ind["board_code"].removeprefix("xq_")
                try:
                    codes = scrape_industry_members(page, ind_code, ind["name"])
                    result.append({**ind, "codes": codes})
                    print(f"  [{i}/{len(industries)}] {ind['name']}：{len(codes)} 只")
                except Exception as e:  # noqa: BLE001
                    print(f"  ⚠️ [{i}/{len(industries)}] {ind['name']} 抓取失败，跳过：{e}")
                _human_wait(page)
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    total_codes = sum(len(it.get("codes", [])) for it in result)
    print(f"✅ 雪球板块同步完成：{len(result)} 个行业，共 {total_codes} 条成分股关系")
    return result


def login() -> None:
    from playwright.sync_api import sync_playwright

    print("即将打开 Edge。请在窗口里登录雪球（若弹滑块，手动拖动完成）。")
    with sync_playwright() as p:
        ctx = open_context(p, headless=False)
        try:
            page = ctx.new_page()
            page.goto(HOME)
            input("登录完成后按回车关闭浏览器…")
        finally:
            ctx.close()
    print("✅ 登录态已保存。")
