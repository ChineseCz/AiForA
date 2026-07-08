"""A股行情快照同步 + 条件选股 + 大V提及匹配。"""
import json
import os
import re
import time
from datetime import date, datetime, timedelta

import config
import db


class InsufficientHistoryError(ValueError):
    """历史K线数据不足，无法计算均线类预设策略。"""


class InsufficientFinanceError(ValueError):
    """财务指标数据不足，无法计算基本面类预设策略。"""

FIELD_WHITELIST = {
    "close": "close",
    "change_pct": "change_pct",
    "volume": "volume",
    "amount": "amount",
    "turnover_rate": "turnover_rate",
    "pe_ttm": "pe_ttm",
    "pb": "pb",
    "total_mv": "total_mv",
    "circ_mv": "circ_mv",
}
OP_WHITELIST = {">", ">=", "<", "<=", "==", "!="}

# 雪球标记格式，如 $贵州茅台(SH600519)$
TICKER_RE = re.compile(r"\$[^$()]+\((?:SZ|SH|BJ)?(\d{6})\)\$")

# 新浪财经 A股全市场行情接口（东方财富的 82.push2.eastmoney.com 在部分网络环境下连接不稳定，改用新浪源）
_SINA_COUNT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount"
_SINA_DATA_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
_SINA_PAGE_SIZE = 80


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_spot_snapshot() -> list[dict]:
    """拉取全市场A股实时快照（新浪财经接口，逐页拉取约5000+只股票）。"""
    import requests

    r = requests.get(_SINA_COUNT_URL, params={"node": "hs_a"}, timeout=10)
    total = int(re.findall(r"\d+", r.text)[0])
    pages = (total + _SINA_PAGE_SIZE - 1) // _SINA_PAGE_SIZE

    rows = []
    for page in range(1, pages + 1):
        r = requests.get(
            _SINA_DATA_URL,
            params={
                "page": str(page), "num": str(_SINA_PAGE_SIZE), "sort": "symbol",
                "asc": "1", "node": "hs_a", "symbol": "", "_s_r_a": "page",
            },
            timeout=10,
        )
        items = r.json()
        for it in items:
            code = it.get("code")
            if not code:
                continue
            rows.append({
                "code": code,
                "name": it.get("name"),
                "close": _to_float(it.get("trade")),
                "change_pct": _to_float(it.get("changepercent")),
                "volume": _to_float(it.get("volume")),
                "amount": _to_float(it.get("amount")),
                "turnover_rate": _to_float(it.get("turnoverratio")),
                "pe_ttm": _to_float(it.get("per")),
                "pb": _to_float(it.get("pb")),
                "total_mv": _to_float(it.get("mktcap")),
                "circ_mv": _to_float(it.get("nmc")),
                "high": _to_float(it.get("high")),
                "low": _to_float(it.get("low")),
                "open": _to_float(it.get("open")),
                "pre_close": _to_float(it.get("settlement")),
            })
        if page % 10 == 0 or page == pages:
            print(f"… 第 {page}/{pages} 页 …")
    return rows


def sync_daily_snapshot() -> int:
    """拉快照并落库，供 CLI 和后台任务共用。"""
    print("… 拉取全市场行情快照 …")
    rows = fetch_spot_snapshot()
    trade_date = date.today().isoformat()
    n = db.save_snapshot(trade_date, rows)
    print(f"✅ 已写入 {n} 条快照（{trade_date}）")
    return n


def build_where(conditions: list[dict]) -> tuple[str, list]:
    """把结构化条件转成参数化 SQL 片段。字段/操作符必须在白名单内，否则抛 ValueError。"""
    where_sql = ""
    params: list = []
    for cond in conditions or []:
        field = FIELD_WHITELIST.get(cond.get("field"))
        op = cond.get("op")
        if field is None or op not in OP_WHITELIST:
            raise ValueError(f"非法筛选条件: {cond}")
        try:
            value = float(cond.get("value"))
        except (TypeError, ValueError):
            raise ValueError(f"非法数值: {cond}")
        where_sql += f" AND {field} {op} ?"
        params.append(value)
    return where_sql, params


def pinyin_abbr(text: str) -> str:
    """中文转拼音首字母缩写，如 "贵州茅台" -> "GZMT"，用于名称模糊搜索。"""
    from pypinyin import lazy_pinyin, Style

    return "".join(lazy_pinyin(text or "", style=Style.FIRST_LETTER)).upper()


def match_name_query(candidates: list[dict], query: str) -> list[dict]:
    """按股票名称/代码/拼音缩写做模糊匹配（子串），候选集通常已被其它条件筛小。"""
    q = (query or "").strip()
    if not q:
        return candidates
    q_upper = q.upper()
    out = []
    for row in candidates:
        name, code = row.get("name") or "", row.get("code") or ""
        if q in name or q in code or q_upper in pinyin_abbr(name):
            out.append(row)
    return out


# 新浪财经历史K线接口（东方财富历史K线域名同样在当前网络下会间歇性连接reset，改用新浪源）
_SINA_HIST_URL = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"


def _sina_symbol(code: str) -> str:
    if code.startswith(("4", "8")) or code.startswith("92"):
        return "bj" + code  # 北交所：老代码4/8开头，新代码段用92开头
    if code.startswith(("6", "9")):
        return "sh" + code
    return "sz" + code


def _history_api_url(code: str, days: int) -> str:
    return f"{_SINA_HIST_URL}?symbol={_sina_symbol(code)}&scale=240&ma=no&datalen={days}"


# 新浪财经个股资讯页（GBK编码，跟板块分类接口 newFLJK.php 同一路数据源，同样的编码坑）。
_SINA_NEWS_URL = "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php"
_NEWS_ITEM_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})&nbsp;&nbsp;<a target='_blank' href='([^']+)'>([^<]+)</a>"
)


def fetch_stock_news(code: str, days: int = 14, max_pages: int = 5) -> list[dict]:
    """拉取个股相关新闻（新浪财经个股资讯页），按天数过滤，倒序（最新在前）。
    页面本身按时间倒序排列，翻到整页最旧一条都早于截止日期就停，不用翻到底。
    单纯是补充信息，任何请求失败都吞掉打日志，返回已拿到的部分，不影响基本面页其余内容。"""
    import requests

    cutoff = date.today() - timedelta(days=days)
    symbol = _sina_symbol(code)
    items: list[dict] = []
    seen_urls: set[str] = set()

    for page in range(1, max_pages + 1):
        try:
            r = requests.get(_SINA_NEWS_URL, params={"symbol": symbol, "Page": str(page)}, timeout=10)
            r.encoding = "gbk"
            html = r.text
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 新闻拉取失败（{code} 第{page}页）：{e}")
            break

        matches = _NEWS_ITEM_RE.findall(html)
        if not matches:
            break

        for d, t, url, title in matches:
            item_date = datetime.strptime(d, "%Y-%m-%d").date()
            if item_date < cutoff or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append({"date": d, "time": t, "title": title.strip(), "url": url})

        oldest_on_page = min(datetime.strptime(d, "%Y-%m-%d").date() for d, _, _, _ in matches)
        if oldest_on_page < cutoff:
            break  # 翻到比截止日期更早了，后面页更旧，不用继续翻

    items.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
    return items


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
    """一次性批量回补全市场历史K线（供 stock-backfill 命令使用）。

    新浪该接口对纯 requests 请求的反爬阈值很低——实测约250只顺序请求后就返回456永久拒绝，
    且这个拒绝状态跟IP绑定，短时间内不会自行解除。但同一个接口，改用真实浏览器（Edge+持久化
    profile，跟雪球抓取用的是同一套方案）在页面内发起同源fetch，实测连续500只0失败——说明反爬
    识别的是"是否为真实浏览器"的请求指纹，而不是纯粹按IP限流。因此这里用 Playwright 驱动真实
    Edge 完成整个回补，比之前"降速硬等封禁解除"的方案更快也更可靠：约0.6~0.8秒/只，全量5526只
    约1小时（会弹出一个可见的浏览器窗口，跑完自动关闭，期间不要手动操作这个窗口）。
    """
    import random

    from playwright.sync_api import sync_playwright

    codes = [r["code"] for r in db.get_latest_rows() if r.get("code")]
    today = date.today().isoformat()
    total = len(codes)
    ok, fail = 0, 0
    if not codes:
        print("⚠️ 还没有行情快照，请先运行 python main.py stock-sync")
        return 0, 0

    profile_dir = os.path.join(config.DATA_DIR, "edge_profile_stock")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel="msedge",
            headless=config.HEADLESS,
            locale="zh-CN",
            viewport=None,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = ctx.new_page()
            # 直接导航到接口URL（而不是先开首页再跨域fetch）：两者同源，跳过CORS，顺带完成WAF预热。
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
                            "open": _to_float(it.get("open")),
                            "close": _to_float(it.get("close")),
                            "high": _to_float(it.get("high")),
                            "low": _to_float(it.get("low")),
                            "volume": _to_float(it.get("volume")),
                        })
                    if bars:
                        db.save_history_bars(bars)
                    ok += 1
                    consec_fail = 0
                else:
                    fail += 1
                    consec_fail += 1
                    if consec_fail >= 10:
                        print(f"⚠️ 连续 {consec_fail} 只失败，暂停60秒后继续（可能触发了新的反爬规则）…")
                        time.sleep(60)
                        consec_fail = 0

                if i % 50 == 0 or i == total:
                    print(f"… 已回补 {i}/{total} 只（成功{ok}/失败{fail}） …")
                time.sleep(random.uniform(delay * 0.6, delay * 1.4))
        finally:
            ctx.close()

    print(f"✅ 历史K线回补完成：成功 {ok} 只，失败 {fail} 只")
    return ok, fail


# 东方财富"业绩报表"接口：批量拉全市场最新一期财务指标（EPS/ROE/净利润同比/营收同比/毛利率）。
_EM_FINANCE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_FINANCE_REPORT = "RPT_LICO_FN_CPD"
_EM_FINANCE_COLUMNS = "SECURITY_CODE,SECURITY_NAME_ABBR,SECUCODE,REPORTDATE,BASIC_EPS,WEIGHTAVG_ROE,YSTZ,SJLTZ,XSMLL"
_EM_FINANCE_PAGE_SIZE = 500
_EM_HEADERS = {"Referer": "https://data.eastmoney.com/"}


def _latest_finance_report_date() -> str:
    """财报是按季度批量披露的，用当前数据里最新的 REPORTDATE 而不是硬编码日期，
    这样进入下一个报告期（比如中报陆续披露）后无需改代码就能跟着切换。"""
    import requests

    r = requests.get(
        _EM_FINANCE_URL,
        params={
            "sortColumns": "REPORTDATE", "sortTypes": "-1", "pageSize": "1", "pageNumber": "1",
            "reportName": _EM_FINANCE_REPORT, "columns": "REPORTDATE",
        },
        headers=_EM_HEADERS, timeout=10,
    )
    data = r.json()["result"]["data"]
    return data[0]["REPORTDATE"].split(" ")[0]


def fetch_finance_snapshot() -> list[dict]:
    """拉取全市场A股最新一期财务指标快照（东方财富业绩报表接口，逐页拉取）。"""
    import requests

    report_date = _latest_finance_report_date()
    rows = []
    page, pages = 1, 1
    while page <= pages:
        r = requests.get(
            _EM_FINANCE_URL,
            params={
                "sortColumns": "SECURITY_CODE", "sortTypes": "1",
                "pageSize": str(_EM_FINANCE_PAGE_SIZE), "pageNumber": str(page),
                "reportName": _EM_FINANCE_REPORT, "columns": _EM_FINANCE_COLUMNS,
                "filter": f"(REPORTDATE='{report_date}')",
            },
            headers=_EM_HEADERS, timeout=10,
        )
        result = r.json()["result"]
        pages = result["pages"]
        for it in result["data"]:
            secucode = it.get("SECUCODE") or ""
            if not secucode.endswith((".SH", ".SZ", ".BJ")):
                continue  # 排除新三板等非A股代码
            rows.append({
                "code": it.get("SECURITY_CODE"),
                "name": it.get("SECURITY_NAME_ABBR"),
                "report_date": report_date,
                "eps": _to_float(it.get("BASIC_EPS")),
                "roe": _to_float(it.get("WEIGHTAVG_ROE")),
                "net_profit_yoy": _to_float(it.get("SJLTZ")),
                "revenue_yoy": _to_float(it.get("YSTZ")),
                "gross_margin": _to_float(it.get("XSMLL")),
            })
        if page % 5 == 0 or page == pages:
            print(f"… 第 {page}/{pages} 页 …")
        page += 1
    return rows


def sync_finance_snapshot() -> int:
    """拉财务指标快照并落库，供 CLI 和后台任务共用。"""
    print("… 拉取全市场最新财报指标 …")
    rows = fetch_finance_snapshot()
    n = db.save_finance(rows)
    print(f"✅ 已写入 {n} 条财务指标（报告期 {rows[0]['report_date'] if rows else '-'}）")
    return n


def is_st_or_s(name: str) -> bool:
    name = name or ""
    return "ST" in name or "S" in name


def is_main_board(code: str) -> bool:
    return not (code or "").startswith(("688", "689", "300", "301"))


def is_kechuang(code: str) -> bool:
    return (code or "").startswith("688")


def _moving_avg(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
        else:
            out.append(sum(values[i + 1 - window: i + 1]) / window)
    return out


def _crossed_up(fast: list[float | None], slow: list[float | None], t: int) -> bool:
    if fast[t] is None or slow[t] is None or fast[t - 1] is None or slow[t - 1] is None:
        return False
    return fast[t] >= slow[t] and fast[t - 1] < slow[t - 1]


def _ma_cross_metrics(bars: list[dict]) -> dict | None:
    """给一只股票近90天K线，算 MA5/10/20 及金叉/5日涨幅指标；数据不足返回 None。"""
    if len(bars) < 23:
        return None
    closes = [b["close"] for b in bars]
    ma5 = _moving_avg(closes, 5)
    ma10 = _moving_avg(closes, 10)
    ma20 = _moving_avg(closes, 20)
    n = len(closes)
    if ma20[-1] is None or n < 6 or closes[-6] in (None, 0):
        return None
    return {
        "closes": closes, "ma5": ma5, "ma10": ma10, "ma20": ma20,
        "cross1_in_3days": any(_crossed_up(ma5, ma10, n - 1 - k) for k in range(3) if n - 1 - k >= 1),
        "cross23_in_3days": any(
            _crossed_up(ma10, ma20, n - 1 - k) or _crossed_up(ma5, ma20, n - 1 - k)
            for k in range(3) if n - 1 - k >= 1
        ),
        "rise5": closes[-1] / closes[-6] - 1 > 0.03,
    }


def _load_ma_series(candidates: set[str]) -> dict[str, list[dict]]:
    since = (date.today() - timedelta(days=90)).isoformat()
    hist = db.get_history_since(since)
    series: dict[str, list[dict]] = {}
    for row in hist:
        if row["code"] in candidates:
            series.setdefault(row["code"], []).append(row)
    return series


def screen_ma_cross(limit: int = 200) -> list[dict]:
    """预设策略「严格买点」：均线金叉（MA5/10/20 3日内金叉）+ 近5日涨幅>3% + 收盘价>MA20 + 多头排列（主板，非ST/S/停牌）。"""
    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and is_main_board(r["code"]) and not is_st_or_s(r.get("name"))
        and r.get("volume")
    }
    if not candidates:
        return []

    series = _load_ma_series(candidates)
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < 23:
        raise InsufficientHistoryError("历史数据不足，请先运行 python main.py stock-backfill 回补历史K线")

    hits = []
    for code, bars in series.items():
        m = _ma_cross_metrics(bars)
        if not m or not (m["cross1_in_3days"] and m["cross23_in_3days"] and m["rise5"]):
            continue
        price_above20 = m["closes"][-1] > m["ma20"][-1]
        duotou = m["ma5"][-1] is not None and m["ma10"][-1] is not None and m["ma5"][-1] > m["ma10"][-1] > m["ma20"][-1]
        if price_above20 and duotou:
            hits.append(dict(latest_by_code.get(code, {"code": code})))

    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


def screen_ma_cross2(limit: int = 200) -> list[dict]:
    """预设策略「宽松买点」：均线金叉变体——MA5/10金叉近3日 + (MA10/20或MA5/20金叉)近3日 + 5日涨幅>3%，
    只剔除科创板（688开头），不要求"站上MA20"和"多头排列"（对应用户提供的通达信公式，
    仅排除 STRFIND(STKLABEL,'688',1)=1，创业板/北交所不排除）。"""
    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and not is_kechuang(r["code"]) and not is_st_or_s(r.get("name"))
        and r.get("volume")
    }
    if not candidates:
        return []

    series = _load_ma_series(candidates)
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < 23:
        raise InsufficientHistoryError("历史数据不足，请先运行 python main.py stock-backfill 回补历史K线")

    hits = []
    for code, bars in series.items():
        m = _ma_cross_metrics(bars)
        if m and m["cross1_in_3days"] and m["cross23_in_3days"] and m["rise5"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))

    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


def _golden_cross_metrics(bars: list[dict]) -> dict | None:
    """给一只股票近90天K线，算近4日(含今日) MACD/KDJ 是否各出现过至少一次金叉；数据不足返回 None。"""
    if len(bars) < 23:
        return None
    closes = [b["close"] for b in bars]
    dif, dea, _ = compute_macd(closes)
    k_list, d_list, _ = compute_kdj(bars)
    n = len(closes)
    return {
        "macd_recent": any(_crossed_up(dif, dea, n - 1 - i) for i in range(4) if n - 1 - i >= 1),
        "kdj_recent": any(_crossed_up(k_list, d_list, n - 1 - i) for i in range(4) if n - 1 - i >= 1),
    }


def screen_golden_cross(limit: int = 200) -> list[dict]:
    """预设策略「金叉买点」：近4日内(含今日) MACD金叉(DIF上穿DEA)>=1次 且 KDJ金叉(K上穿D)>=1次
    （对应用户提供的通达信公式，不限板块，仅排除ST/S/停牌）。"""
    latest = db.get_latest_rows()
    latest_by_code = {r["code"]: r for r in latest}
    candidates = {
        r["code"] for r in latest
        if r.get("code") and not is_st_or_s(r.get("name")) and r.get("volume")
    }
    if not candidates:
        return []

    series = _load_ma_series(candidates)
    max_len = max((len(v) for v in series.values()), default=0)
    if max_len < 23:
        raise InsufficientHistoryError("历史数据不足，请先运行 python main.py stock-backfill 回补历史K线")

    hits = []
    for code, bars in series.items():
        m = _golden_cross_metrics(bars)
        if m and m["macd_recent"] and m["kdj_recent"]:
            hits.append(dict(latest_by_code.get(code, {"code": code})))

    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


def screen_fund_ok(limit: int = 200) -> list[dict]:
    """预设策略「基本面达标」：净利润同比增长>0、EPS>0.1、ROE>3%、营收同比增长>10%、
    销售毛利率>10%，且非ST（对应用户提供的通达信公式，选股条件即 fund_ok，不含技术面）。"""
    fin_map = db.get_finance_map()
    if not fin_map:
        raise InsufficientFinanceError("还没有财务指标数据，请先运行 python main.py stock-sync-finance 同步")

    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}

    hits = []
    for code, fin in fin_map.items():
        quote = latest_by_code.get(code)
        if not quote:
            continue
        if is_st_or_s(quote.get("name") or fin.get("name")):
            continue
        net_profit_yoy, eps, roe, revenue_yoy, gross_margin = (
            fin.get("net_profit_yoy"), fin.get("eps"), fin.get("roe"),
            fin.get("revenue_yoy"), fin.get("gross_margin"),
        )
        if None in (net_profit_yoy, eps, roe, revenue_yoy, gross_margin):
            continue
        if net_profit_yoy > 0 and eps > 0.1 and roe > 3 and revenue_yoy > 10 and gross_margin > 10:
            row = dict(quote)
            row.update(
                eps=eps, roe=roe, net_profit_yoy=net_profit_yoy,
                revenue_yoy=revenue_yoy, gross_margin=gross_margin, report_date=fin.get("report_date"),
            )
            hits.append(row)

    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


_PRESET_STRATEGIES = {
    "ma_cross": screen_ma_cross,
    "ma_cross2": screen_ma_cross2,
    "golden_cross": screen_golden_cross,
    "fund_ok": screen_fund_ok,
}


def screen_combined(strategy_keys: list[str], limit: int = 200) -> list[dict]:
    """跑选中的多个预设策略，取交集（按 code），供网页多选组合筛选用。"""
    keys = [k for k in dict.fromkeys(strategy_keys or []) if k in _PRESET_STRATEGIES]
    if not keys:
        raise ValueError("请至少选择一个预设策略")

    results = {k: _PRESET_STRATEGIES[k](100000) for k in keys}

    common_codes = None
    for hits in results.values():
        codes = {r["code"] for r in hits if r.get("code")}
        common_codes = codes if common_codes is None else (common_codes & codes)
    if not common_codes:
        return []

    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    merged: dict[str, dict] = {}
    for hits in results.values():
        for r in hits:
            code = r.get("code")
            if code in common_codes:
                row = merged.setdefault(code, dict(latest_by_code.get(code, {"code": code})))
                row.update({k: v for k, v in r.items() if v is not None})

    combined_hits = list(merged.values())
    combined_hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return combined_hits[:limit]


def screen_combined_all(strategy_keys: list[str], conditions: list[dict], limit: int = 200) -> list[dict]:
    """预设策略 + 自定义筛选条件 一起取交集（两者都可留空，但至少要有一个）。"""
    keys = [k for k in dict.fromkeys(strategy_keys or []) if k in _PRESET_STRATEGIES]
    has_presets = bool(keys)
    has_conditions = bool(conditions)
    if not has_presets and not has_conditions:
        raise ValueError("请至少选择一个预设策略，或填写筛选条件")

    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}

    preset_rows: dict[str, dict] = {}
    if has_presets:
        results = {k: _PRESET_STRATEGIES[k](100000) for k in keys}
        common = None
        for hits in results.values():
            codes = {r["code"] for r in hits if r.get("code")}
            common = codes if common is None else (common & codes)
        for hits in (results.values() if common else []):
            for r in hits:
                code = r.get("code")
                if code in common:
                    row = preset_rows.setdefault(code, {})
                    row.update({k: v for k, v in r.items() if v is not None})

    cond_rows: dict[str, dict] = {}
    if has_conditions:
        trade_date = db.get_latest_trade_date()
        where_sql, params = build_where(conditions)
        cond_rows = {
            r["code"]: r for r in db.screen_stocks(trade_date, where_sql, params, 100000) if r.get("code")
        }

    if has_presets and has_conditions:
        common_codes = set(preset_rows) & set(cond_rows)
    elif has_presets:
        common_codes = set(preset_rows)
    else:
        common_codes = set(cond_rows)
    if not common_codes:
        return []

    merged: dict[str, dict] = {}
    for code in common_codes:
        row = dict(latest_by_code.get(code, {"code": code}))
        row.update({k: v for k, v in preset_rows.get(code, {}).items() if v is not None})
        row.update({k: v for k, v in cond_rows.get(code, {}).items() if v is not None})
        merged[code] = row

    hits = list(merged.values())
    hits.sort(key=lambda r: r.get("change_pct") or 0, reverse=True)
    return hits[:limit]


def _recent_combined_text(days: int, user_id: str) -> str:
    """拼出最近N天目标大V（不传则全部大V）的帖子文本，供提及/板块匹配复用。"""
    user_ids = [user_id] if user_id else [uid for uid, _ in db.get_distinct_users()]
    texts = db.get_recent_texts(user_ids, days)
    return "\n".join(t for _, t in texts)


def match_mentions(candidates: list[dict], days: int, user_id: str) -> list[dict]:
    """在候选集（价格/财务条件筛完的小结果集）里，过滤出被大V最近提及的。"""
    if not candidates:
        return []
    combined_text = _recent_combined_text(days, user_id)
    if not combined_text:
        return []
    coded_mentions = set(TICKER_RE.findall(combined_text))
    out = []
    for row in candidates:
        code = row.get("code") or ""
        name = row.get("name") or ""
        if code in coded_mentions or (name and name in combined_text):
            out.append(row)
    return out


def get_stock_mentions(code: str, name: str, days: int = 90, limit: int = 20) -> list[dict]:
    """反查某只股票最近被大V提及的帖子，供个股详情页用。判定口径跟 match_mentions 一致
    （$xxx(SH600519)$ 代码标记或股票名子串），只是方向反过来——按帖子找股票 vs 按股票找帖子。"""
    since = (date.today() - timedelta(days=days)).isoformat()
    terms = [t for t in (code, name) if t]
    if not terms:
        return []
    candidates = db.search_posts_containing(terms, since, limit=200)
    out = []
    for p in candidates:
        combined = (p.get("text") or "") + (p.get("title") or "")
        if (code and code in TICKER_RE.findall(combined)) or (name and name in combined):
            out.append(p)
    return out[:limit]


# ===== 以下供板块（行业/概念）筛选使用 =====
# 东方财富 push2.eastmoney.com 在本环境下经常连接被reset（跟第35行行情快照绕开push2是同一个坑），
# 改用新浪财经的板块分类接口，跟成分股查询共用行情快照那套 getHQNodeData 接口。
_SINA_CLASS_URL = "http://vip.stock.finance.sina.com.cn/q/view/newFLJK.php"


def _fetch_board_list(param: str, kind: str) -> list[dict]:
    """拉某一类（行业/概念）板块名单。param 如 'class_dp'（行业）/'class'（概念）。"""
    import requests

    r = requests.get(_SINA_CLASS_URL, params={"param": param}, timeout=10)
    text = r.content.decode("gbk", errors="replace")
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0)) if m else {}
    rows = []
    for board_code, raw in data.items():
        parts = raw.split(",")
        if board_code and len(parts) > 1 and parts[1]:
            rows.append({"board_code": board_code, "name": parts[1], "kind": kind})
    return rows


def sync_sector_catalog() -> int:
    """拉行业+概念板块名单（不含成分股），供板块筛选的下拉框/关键词字典用。"""
    rows = _fetch_board_list("class_dp", "industry") + _fetch_board_list("class", "concept")
    n = db.save_sector_catalog(rows)
    print(f"✅ 已同步 {n} 个板块（行业+概念）")
    return n


def fetch_board_members(board_code: str) -> list[str]:
    """拉某个板块的成分股代码列表，分页拉全量（新浪 getHQNodeData，跟行情快照同一接口）。

    行业板块成分股数量通常远多于概念板块，分页更多，命中单页flaky空响应（`r.json()`抛
    `Expecting value`）的概率也更高——原来任何一页失败都会让整个板块直接报废（哪怕前面
    几页都成功了）。这里给单页请求加一次短重试，避免偶发的单页空响应拖垮整个板块。
    """
    import requests

    codes: list[str] = []
    page = 1
    while True:
        for attempt in range(2):
            r = requests.get(
                _SINA_DATA_URL,
                params={
                    "page": str(page), "num": str(_SINA_PAGE_SIZE), "sort": "symbol",
                    "asc": "1", "node": board_code, "symbol": "", "_s_r_a": "page",
                },
                timeout=10,
            )
            try:
                items = r.json()
                break
            except ValueError:
                if attempt == 1:
                    raise
                time.sleep(0.4)
        if not isinstance(items, list) or not items:
            break
        codes.extend(it["code"] for it in items if it.get("code"))
        if len(items) < _SINA_PAGE_SIZE:
            break
        page += 1
    return codes


def get_sector_members(sector: str) -> list[str]:
    """先查缓存，没有/过期则实时拉取并回写缓存。"""
    codes = db.get_sector_members_cached(sector)
    if codes is not None:
        return codes
    board_code = db.get_board_code(sector)
    if not board_code:
        return []
    codes = fetch_board_members(board_code)
    db.save_sector_members(sector, board_code, codes)
    return codes


def sync_all_sector_members() -> int:
    """全量同步所有板块（行业+概念）的成分股。get_sector_members 平时是懒加载——只有筛选时
    用到的板块才会去拉——这里主动把 sector_catalog 里的板块全部过一遍（沿用同一套7天缓存，
    已是新鲜的板块会直接跳过），让个股详情页的「所属板块」反查覆盖全市场。个别板块偶发请求失败
    （空响应/限流）不应中断整个同步，跳过并继续，最后汇总失败数。"""
    catalog = db.get_sector_catalog()
    if not catalog:
        raise ValueError("还没有板块名单，请先运行板块名单同步（sync_sector_catalog）")
    total = len(catalog)
    n_codes = 0
    n_failed = 0
    for i, sec in enumerate(catalog, 1):
        try:
            codes = get_sector_members(sec["name"])
            n_codes += len(codes)
        except Exception as e:  # noqa: BLE001
            n_failed += 1
            print(f"⚠️ 板块「{sec['name']}」同步失败，跳过：{e}")
        if i % 20 == 0 or i == total:
            print(f"… 已同步 {i}/{total} 个板块的成分股 …")
    print(f"✅ 板块成分股全量同步完成：{total} 个板块（失败 {n_failed} 个），共 {n_codes} 条股票-板块关系")
    return total


def extract_sectors_from_text(text: str, catalog_names: list[str]) -> set[str]:
    """在文本里做板块名称子串匹配（板块名一般2-6字，直接 contains 判断即可）。"""
    if not text:
        return set()
    return {name for name in catalog_names if name and name in text}


def derive_bullish_sectors(days: int, user_id: str) -> list[str]:
    """从大V最近N天帖子文本里，反查提到了哪些已知板块名称。"""
    combined_text = _recent_combined_text(days, user_id)
    if not combined_text:
        return []
    catalog_names = [c["name"] for c in db.get_sector_catalog()]
    return sorted(extract_sectors_from_text(combined_text, catalog_names))


def match_sector(candidates: list[dict], sector_names: list[str]) -> list[dict]:
    """按板块名称列表反查成分股代码集合（多个板块取并集），过滤候选集。"""
    if not candidates or not sector_names:
        return []
    codes: set[str] = set()
    for name in sector_names:
        codes.update(get_sector_members(name))
    return [row for row in candidates if (row.get("code") or "") in codes]


# ===== 以下供个股日线详情页使用 =====
def _ema(values: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    out: list[float] = []
    prev = None
    for v in values:
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def compute_macd(closes: list[float]) -> tuple[list[float], list[float], list[float]]:
    """标准 MACD：DIF=EMA12-EMA26，DEA=EMA9(DIF)，柱=2*(DIF-DEA)。"""
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    dif = [a - b for a, b in zip(ema12, ema26)]
    dea = _ema(dif, 9)
    macd = [2 * (a - b) for a, b in zip(dif, dea)]
    return dif, dea, macd


def compute_kdj(bars: list[dict]) -> tuple[list[float], list[float], list[float]]:
    """标准 KDJ(9,3,3)：RSV 用近9日最高/最低，K/D 递归 SMA，初值50。"""
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    k_list: list[float] = []
    d_list: list[float] = []
    j_list: list[float] = []
    prev_k, prev_d = 50.0, 50.0
    for i in range(len(bars)):
        window_lo = lows[max(0, i - 8): i + 1]
        window_hi = highs[max(0, i - 8): i + 1]
        lo, hi = min(window_lo), max(window_hi)
        rsv = 50.0 if hi == lo else (closes[i] - lo) / (hi - lo) * 100
        k_val = prev_k * 2 / 3 + rsv / 3
        d_val = prev_d * 2 / 3 + k_val / 3
        j_val = 3 * k_val - 2 * d_val
        k_list.append(k_val)
        d_list.append(d_val)
        j_list.append(j_val)
        prev_k, prev_d = k_val, d_val
    return k_list, d_list, j_list


def daily_signal_series(bars: list[dict]) -> tuple[list[bool], list[bool]]:
    """把 `_ma_cross_metrics` 的"严格/宽松买点"判断从只算最后一天，泛化成对历史每天都算一遍。"""
    closes = [b["close"] for b in bars]
    n = len(closes)
    ma5 = _moving_avg(closes, 5)
    ma10 = _moving_avg(closes, 10)
    ma20 = _moving_avg(closes, 20)
    strict_ok = [False] * n
    loose_ok = [False] * n
    for t in range(n):
        if ma20[t] is None or t < 5 or closes[t - 5] in (None, 0):
            continue
        cross1 = any(_crossed_up(ma5, ma10, t - k) for k in range(3) if t - k >= 1)
        cross23 = any(
            _crossed_up(ma10, ma20, t - k) or _crossed_up(ma5, ma20, t - k)
            for k in range(3) if t - k >= 1
        )
        rise5 = closes[t] / closes[t - 5] - 1 > 0.03
        loose_ok[t] = bool(cross1 and cross23 and rise5)
        if loose_ok[t]:
            price_above20 = closes[t] > ma20[t]
            duotou = ma5[t] is not None and ma10[t] is not None and ma5[t] > ma10[t] > ma20[t]
            strict_ok[t] = bool(price_above20 and duotou)
    return strict_ok, loose_ok


def daily_sell_signal_series(closes: list[float], ma5: list[float | None], ma10: list[float | None],
                              dif: list[float], dea: list[float]) -> tuple[list[bool], list[bool]]:
    """卖点指标：①中期反转=MA5下穿MA10（趋势破）或MACD死叉；②短期止损=收盘价下穿MA5。"""
    n = len(closes)
    mid_reverse_ok = [False] * n
    stop_loss_ok = [False] * n
    for t in range(1, n):
        trend_break = (
            ma5[t] is not None and ma10[t] is not None and ma5[t - 1] is not None and ma10[t - 1] is not None
            and ma5[t] < ma10[t] and ma5[t - 1] >= ma10[t - 1]
        )
        macd_dead = dif[t] < dea[t] and dif[t - 1] >= dea[t - 1]
        mid_reverse_ok[t] = bool(trend_break or macd_dead)
        stop_loss_ok[t] = bool(
            ma5[t] is not None and ma5[t - 1] is not None
            and closes[t] < ma5[t] and closes[t - 1] >= ma5[t - 1]
        )
    return mid_reverse_ok, stop_loss_ok


def daily_golden_signal_series(dif: list[float], dea: list[float],
                                k_list: list[float], d_list: list[float]) -> list[bool]:
    """把「金叉买点」（近4日MACD金叉+KDJ金叉各≥1次）泛化成对历史每天都算一遍。"""
    n = len(dif)
    out = [False] * n
    for t in range(n):
        macd_recent = any(_crossed_up(dif, dea, t - i) for i in range(4) if t - i >= 1)
        kdj_recent = any(_crossed_up(k_list, d_list, t - i) for i in range(4) if t - i >= 1)
        out[t] = bool(macd_recent and kdj_recent)
    return out


def get_kline_view(code: str) -> dict:
    """给个股详情页用：日线K线 + MA/MACD/KDJ 指标 + 逐日买卖点信号，供前端画6幅图。"""
    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    name = (latest_by_code.get(code) or {}).get("name") or code

    bars = db.get_history_for_code(code)
    if len(bars) < 23:
        return {"code": code, "name": name, "bars": []}

    closes = [b["close"] for b in bars]
    ma5 = _moving_avg(closes, 5)
    ma10 = _moving_avg(closes, 10)
    ma20 = _moving_avg(closes, 20)
    dif, dea, macd = compute_macd(closes)
    k, d, j = compute_kdj(bars)
    strict_ok, loose_ok = daily_signal_series(bars)
    golden_ok = daily_golden_signal_series(dif, dea, k, d)
    mid_reverse_ok, stop_loss_ok = daily_sell_signal_series(closes, ma5, ma10, dif, dea)

    out_bars = []
    for i, b in enumerate(bars):
        out_bars.append({
            "trade_date": b["trade_date"],
            "open": b["open"] if b["open"] is not None else b["close"],
            "high": b["high"], "low": b["low"], "close": b["close"], "volume": b["volume"],
            "ma5": ma5[i], "ma10": ma10[i], "ma20": ma20[i],
            "dif": dif[i], "dea": dea[i], "macd": macd[i],
            "k": k[i], "d": d[i], "j": j[i],
            "strict_ok": strict_ok[i], "loose_ok": loose_ok[i], "golden_ok": golden_ok[i],
            "mid_reverse_ok": mid_reverse_ok[i], "stop_loss_ok": stop_loss_ok[i],
        })
    return {"code": code, "name": name, "bars": out_bars}


def get_fundamentals_view(code: str, mention_days: int = 90) -> dict:
    """给个股详情页「基本面」区域用：估值快照 + 最新财报指标 + 所属板块 + 大V提及帖子。"""
    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    quote = latest_by_code.get(code) or {}
    name = quote.get("name") or code
    return {
        "code": code,
        "name": name,
        "quote": {
            "pe_ttm": quote.get("pe_ttm"),
            "pb": quote.get("pb"),
            "total_mv": quote.get("total_mv"),
            "circ_mv": quote.get("circ_mv"),
        },
        "finance": db.get_finance_by_code(code),
        "sectors": db.get_sectors_by_code(code),
        "mentions": get_stock_mentions(code, name, days=mention_days, limit=20),
    }


def group_members_view(group_id: int) -> list[dict]:
    """给股票分组页用：组内股票 + 最新行情快照（收盘/涨跌幅/市盈率等），供渲染同款结果表格。"""
    latest_by_code = {r["code"]: r for r in db.get_latest_rows()}
    rows = []
    for m in db.get_group_members(group_id):
        row = dict(latest_by_code.get(m["code"]) or {})
        row["code"] = m["code"]
        row["name"] = row.get("name") or m["name"] or m["code"]
        row["added_at"] = m["added_at"]
        rows.append(row)
    return rows
