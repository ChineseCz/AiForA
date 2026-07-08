"""雪球抓取（方案 A）：用 Playwright 驱动本机 Edge，复用一个专用浏览器配置目录。

为什么这么做：雪球用阿里云 WAF 反爬，纯 requests / 无头浏览器一访问大V主页就弹滑块。
用"带登录态的真实浏览器"去访问，等于你自己在用浏览器看公开帖子——不绕过任何验证。

流程：
  1. 首次运行 `python main.py login`，在弹出的 Edge 里登录雪球（有滑块就手动拖一下）。
     登录态会保存在 data/edge_profile，之后基本不用再登。
  2. `python main.py crawl` 打开同一个配置的 Edge，逐个大V主页滚动加载，
     抓取页面自己发出的 user_timeline.json 数据，去重入库。

接口和反爬策略会变。如果抓不到，多半是登录态过期，重跑一次 login 即可。
"""
import json
import random
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

import config
import db

HOME = "https://xueqiu.com"

# 轻量反自动化指纹，配合“真实 Edge + 登录态”降低被识别概率。
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
window.chrome = window.chrome || {runtime: {}};
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
"""


# ---------- 文本处理 ----------
def clean_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def ms_to_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d")


# ---------- 随机延时（固定节奏最容易被反爬识别，这里全部加抖动）----------
def _rand_secs(base: float | None = None, spread: float = 1.6) -> float:
    """返回 [base, base*spread] 之间的随机秒数。"""
    base = config.REQUEST_DELAY if base is None else base
    return random.uniform(base, base * spread)


def _human_wait(page) -> None:
    """页面内停顿（翻页/取全文之间），随机抖动。"""
    page.wait_for_timeout(int(_rand_secs() * 1000))


def _human_sleep(base: float | None = None) -> None:
    """进程级停顿（大V之间），随机抖动。"""
    time.sleep(_rand_secs(base))


def normalize_profile_url(user: str) -> str:
    user = user.strip()
    if user.startswith("http"):
        return user
    if user.isdigit():
        return f"{HOME}/u/{user}"
    return f"{HOME}/{user.lstrip('/')}"


def _is_truncated(status: dict) -> bool:
    """时间线接口对"专栏"长文帖子（is_column）返回的 text 直接是空字符串，
    truncated 标记也是 false（不是常规"给预览再标记截断"），必须按 text 为空也当截断处理，
    否则永远不会触发下面的全文补抓，只会存下 title 没有正文（用 /statuses/show.json?id= 验证过确实有全文）。"""
    raw = status.get("text", "") or ""
    if not raw.strip():
        return True
    return bool(status.get("truncated")) or "查看全文" in raw


def extract_images(status: dict) -> list[str]:
    """从雪球单条 status 原始字典里提出配图URL列表（去掉 `!thumb.jpg` 等尺寸后缀取原图，
    缩略图给视觉模型识图时太模糊，实测 3.5KB thumb vs 104KB 原图，文字/图表细节差很多）。

    单图帖子 `pic` 字段就是完整URL（形如 .../<filename>!thumb.jpg）；多图帖子
    （`is_ss_multi_pic`）`image_info_list` 里是各图的 filename，没有完整URL，
    用 `pic` 的主机前缀拼出来（同一 CDN 域名，实测同一帖子内一致）。
    """
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


# ---------- 浏览器上下文 ----------
def open_context(playwright, headless: bool | None = None):
    """打开复用登录态的持久化浏览器上下文。"""
    import os

    os.makedirs(config.PROFILE_DIR, exist_ok=True)
    ctx = playwright.chromium.launch_persistent_context(
        user_data_dir=config.PROFILE_DIR,
        channel="msedge",
        headless=config.HEADLESS if headless is None else headless,
        locale="zh-CN",
        viewport=None,
        args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
    )
    ctx.add_init_script(STEALTH_JS)
    return ctx


def _wait_waf(page, label: str, max_s: int = 60) -> bool:
    """等 WAF 清除；出现滑块时提示用户在窗口里手动完成。"""
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
    """在已通过 WAF 的页面里，用同源 fetch 取长文全文。失败返回 None。"""
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
    """在已通过 WAF 的主页里，用同源 XHR 主动请求某一页时间线。

    返回 (原始JSON文本 | None, 状态)，状态为：
      'ok'      正常拿到数据
      'blocked' 被 WAF 拦截（返回的是 HTML 挑战页）
      'empty'   返回空（通常代表翻到底了）
      'error'   请求异常
    """
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


# ---------- 抓单个用户 ----------
def _day_start_ms(d) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000)


def crawl_user(ctx, user: str, since=None, until=None) -> tuple[str, str, int, int, bool]:
    """抓单个用户。since/until 为 date 对象时，只保留 [since, until] 当天范围内的帖子，
    并在翻到比 since 更早时停止翻页。

    返回 (user_id, user_name, 新增条数, 被WAF拦截次数, 是否因拦截提前停止)。"""
    since_ms = _day_start_ms(since) if since else None
    until_ms = _day_start_ms(until) + 86_400_000 if until else None  # until 当天 23:59:59 含

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

    # 等页面自身加载出第 1 页（借此拿到 user_id，并确认 XHR 能过 WAF）。
    for _ in range(15):
        page.wait_for_timeout(1000)
        if bodies:
            break

    statuses: dict[str, dict] = {}

    def absorb(raw: str) -> tuple[int, int | None]:
        """收下一页数据，返回 (本页新增数, 本页最旧帖的时间戳ms)。"""
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

    # 取 user_id，再用同源 XHR 主动翻页（比依赖滚动稳）。
    uid = ""
    for st in statuses.values():
        uid = str((st.get("user") or {}).get("id") or "")
        if uid:
            break

    # 指定时间段时放开页数上限（靠日期停），否则用 MAX_PAGES。
    has_range = since_ms is not None or until_ms is not None
    page_cap = 2000 if has_range else config.MAX_PAGES

    blocked = 0            # 被 WAF 拦截的请求次数
    stopped_by_block = False

    if uid:
        pg = 2
        while pg <= page_cap:
            raw, status = fetch_timeline_in_page(page, uid, pg)

            if status == "blocked":
                blocked += 1
                # 被拦：回首页重新预热一次（刷新 WAF 通行证），再重试本页。
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
                    break  # 预热后仍被拦，提前停止（更早的可能没抓全）

            if status != "ok" or raw is None:
                break  # empty / error：当作翻到底

            added, page_min = absorb(raw)
            if added == 0:
                break  # 没有更多新帖了
            if since_ms is not None and page_min is not None and page_min < since_ms:
                break  # 翻到比起始日期更早，停

            _human_wait(page)
            if pg % 8 == 0:  # 每翻约 8 页，多歇一会儿，更像真人
                _human_wait(page)
                _human_wait(page)
            pg += 1

    user_id = ""
    user_name = ""
    new_count = 0
    for sid, st in statuses.items():
        uinfo = st.get("user") or {}
        user_id = str(uinfo.get("id") or user_id)
        user_name = uinfo.get("screen_name") or user_name

        created = int(st.get("created_at") or 0)
        # 时间段过滤：范围外的跳过不入库。
        if since_ms is not None and created < since_ms:
            continue
        if until_ms is not None and created >= until_ms:
            continue

        if db.post_exists(sid):
            continue

        text = clean_text(st.get("text", ""))
        if config.FETCH_FULL_TEXT and _is_truncated(st):
            full = fetch_full_text_in_page(page, sid)
            if full and len(full) > len(text):
                text = full
            _human_wait(page)

        db.upsert_post(
            {
                "id": sid,
                "user_id": user_id,
                "user_name": user_name,
                "created_at": created,
                "date": ms_to_date(created) if created else "",
                "text": text,
                "title": st.get("title") or "",
                "url": f"{HOME}{st.get('target', '')}",
                "like_count": int(st.get("like_count") or 0),
                "retweet_count": int(st.get("retweet_count") or 0),
                "reply_count": int(st.get("reply_count") or 0),
                "fav_count": int(st.get("fav_count") or 0),
                "raw_json": "",
                "images": json.dumps(extract_images(st), ensure_ascii=False),
                "fetched_at": int(time.time()),
            }
        )
        new_count += 1

    try:
        page.close()
    except Exception:
        pass
    return user_id, user_name, new_count, blocked, stopped_by_block


# ---------- 对外命令 ----------
def crawl_all(since=None, until=None) -> None:
    if not config.XUEQIU_USERS:
        print("⚠️  .env 里没配置 XUEQIU_USERS，无可抓取对象。")
        return
    if since or until:
        print(f"📅 只抓时间段：{since or '最早'} ~ {until or '至今'}")
    print("🚀 启动浏览器，开始采集…")
    total_blocked = 0
    with sync_playwright() as p:
        ctx = open_context(p)
        try:
            for i, user in enumerate(config.XUEQIU_USERS):
                if i > 0:
                    # 大V之间停顿更久（随机 8~20 秒），不要连珠炮式访问。
                    _human_sleep(8.0)
                print(f"→ 正在抓取 {user} …")
                try:
                    uid, uname, n, blocked, stopped = crawl_user(ctx, user, since, until)
                    total_blocked += blocked
                    msg = f"✅ {uname or uid}（{uid}）：新增 {n} 条"
                    if blocked:
                        msg += f"；⚠️ 被 WAF 拦截 {blocked} 次"
                        if stopped:
                            msg += "，并因此提前停止（更早的帖子可能没抓全，建议稍后重跑同样的命令补齐）"
                    print(msg)
                except Exception as e:  # noqa: BLE001 - 单个用户失败不影响其他人
                    print(f"❌ 抓取失败 {user}：{e}")
        finally:
            try:
                ctx.close()
            except Exception:
                pass
    if total_blocked:
        print(f"\n⚠️  本次共有 {total_blocked} 次请求被 WAF 拦截。"
              f"如担心遗漏，过几分钟用相同命令重跑一遍即可（已抓的会去重，只补缺的）。")


def login() -> None:
    """打开浏览器让用户登录雪球，登录态保存到专用配置目录。"""
    print("即将打开 Edge。请在窗口里登录雪球（若弹滑块，手动拖动完成）。")
    print("登录成功、能看到自己的首页后，回到这个终端按回车关闭。")
    with sync_playwright() as p:
        ctx = open_context(p, headless=False)
        try:
            page = ctx.new_page()
            page.goto(HOME)
            input("登录完成后按回车关闭浏览器…")
        finally:
            ctx.close()
    print("✅ 登录态已保存到 data/edge_profile，之后 crawl 会复用它。")
