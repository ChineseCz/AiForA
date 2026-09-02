"""新浪财经外部数据抓取：板块成分股 + 个股新闻。从旧 stock.py 移植（纯 requests）。

注意 GBK 编码坑：newFLJK/新闻页返回 GBK，需 decode('gbk')。这些在请求期实时抓取，
均为辅助信息，失败吞掉打日志、返回已拿到的部分，不阻塞主流程。
"""
import json
import re
import time
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

_SINA_COUNT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount"
_SINA_DATA_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
_SINA_PAGE_SIZE = 80

# 板块分类接口（GBK 编码，旧概念分类，覆盖面窄且多年未更新——已弃用，仅行业分类 class_dp 还在用）
_SINA_CLASS_URL = "http://vip.stock.finance.sina.com.cn/q/view/newFLJK.php"

# 板块节点树接口（UTF-8 编码），"A股/热门概念" 子树是新浪现在维护的概念板块（chgn_ 前缀，
# 700+个，含 AI应用/具身智能等新概念），比 newFLJK class 的 gn_ 那套（多年未更新）覆盖广得多。
_SINA_NODES_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes"


def fetch_hot_concepts() -> list[dict]:
    """新浪"热门概念"板块名录（chgn_ 前缀），返回 [{"board_code": ..., "name": ..., "kind": "concept"}, ...]。
    成分股走同一套 getHQNodeData 分页接口，用 fetch_board_members(board_code) 即可拉取。
    """
    r = requests.get(_SINA_NODES_URL, timeout=10)
    data = json.loads(r.content.decode("utf-8"))
    a_share = next((c for c in data[1] if c[0] == "A股"), None)
    if not a_share:
        return []
    hot = next((c for c in a_share[1] if c[0] == "热门概念"), None)
    if not hot:
        return []
    return [
        {"board_code": code, "name": name, "kind": "concept"}
        for name, _, code in hot[1] if code and name
    ]


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fetch_market_snapshot(node: str, market_name: str) -> list[dict]:
    """通用市场快照拉取（A股/ETF等）。"""
    r = requests.get(_SINA_COUNT_URL, params={"node": node}, timeout=10)
    total = int(re.findall(r"\d+", r.text)[0])
    pages = (total + _SINA_PAGE_SIZE - 1) // _SINA_PAGE_SIZE

    rows = []
    for page in range(1, pages + 1):
        r = requests.get(
            _SINA_DATA_URL,
            params={
                "page": str(page), "num": str(_SINA_PAGE_SIZE), "sort": "symbol",
                "asc": "1", "node": node, "symbol": "", "_s_r_a": "page",
            },
            timeout=10,
        )
        items = r.json()
        for it in items:
            code = it.get("code")
            if not code:
                continue
            rows.append({
                "code": code, "name": it.get("name"),
                "close": _to_float(it.get("trade")), "change_pct": _to_float(it.get("changepercent")),
                "volume": _to_float(it.get("volume")), "amount": _to_float(it.get("amount")),
                "turnover_rate": _to_float(it.get("turnoverratio")), "pe_ttm": _to_float(it.get("per")),
                "pb": _to_float(it.get("pb")), "total_mv": _to_float(it.get("mktcap")),
                "circ_mv": _to_float(it.get("nmc")), "high": _to_float(it.get("high")),
                "low": _to_float(it.get("low")), "open": _to_float(it.get("open")),
                "pre_close": _to_float(it.get("settlement")),
            })
        if page % 10 == 0 or page == pages:
            print(f"… {market_name} 第 {page}/{pages} 页 …")
    return rows


def fetch_spot_snapshot() -> list[dict]:
    """全市场A股实时快照（逐页拉取约 5000+ 只）。"""
    return _fetch_market_snapshot("hs_a", "A股")


def fetch_etf_snapshot() -> list[dict]:
    """全市场ETF实时快照（逐页拉取约 1600+ 只）。"""
    return _fetch_market_snapshot("etf_hq_fund", "ETF")


def fetch_bond_snapshot() -> list[dict]:
    """全市场可转债实时快照（新浪 hskzz_z 节点）。"""
    r = requests.get(_SINA_COUNT_URL, params={"node": "hskzz_z"}, timeout=10)
    total = int(re.findall(r"\d+", r.text)[0])
    pages = (total + _SINA_PAGE_SIZE - 1) // _SINA_PAGE_SIZE

    rows = []
    for page in range(1, pages + 1):
        r = requests.get(
            _SINA_DATA_URL,
            params={
                "page": str(page), "num": str(_SINA_PAGE_SIZE), "sort": "symbol",
                "asc": "1", "node": "hskzz_z", "symbol": "", "_s_r_a": "page",
            },
            timeout=10,
        )
        for it in r.json():
            code = str(it.get("code") or "")
            # hskzz_z 还会返回少量北交所“定转”，当前转债表按沪深 11/12 开头代码维护。
            if not code.startswith(("11", "12")):
                continue
            rows.append({
                "code": code, "name": it.get("name"),
                "close": _to_float(it.get("trade")),
                "change_pct": _to_float(it.get("changepercent")),
                "volume": _to_float(it.get("volume")),
                "amount": _to_float(it.get("amount")),
                "high": _to_float(it.get("high")), "low": _to_float(it.get("low")),
                "open": _to_float(it.get("open")), "pre_close": _to_float(it.get("settlement")),
                "stock_code": None, "stock_name": None, "convert_price": None,
                "conversion_value": None, "premium_rate": None, "maturity_date": None,
                "rating": None, "redeem_status": None,
            })
        if page % 10 == 0 or page == pages:
            print(f"… 可转债第 {page}/{pages} 页 …")
    return rows


def fetch_bond_basic(code: str) -> dict:
    """从新浪债券资料页读取可转债基础资料和最新转股价。"""
    market = "sh" if code.startswith("11") else "sz"
    symbol = f"{market}{code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    result = {"code": code, "issuer_name": None, "convert_price": None, "maturity_date": None, "rating": None}

    def table_map(url: str) -> dict[str, str]:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = "gb2312"
        soup = BeautifulSoup(response.text, "html.parser")
        values: dict[str, str] = {}
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            for i in range(0, len(cells) - 1, 2):
                if cells[i] and cells[i + 1]:
                    values[cells[i]] = cells[i + 1]
        return values

    info = table_map(f"https://money.finance.sina.com.cn/bond/info/{symbol}.html")
    terms = table_map(f"https://money.finance.sina.com.cn/bond/convertItem/{symbol}.html")
    result["maturity_date"] = info.get("到期日") or info.get("到期")
    result["rating"] = info.get("信用等级")
    value = terms.get("最新转换价格（元）") or terms.get("最新转换价格(元)")
    result["convert_price"] = _to_float(value)
    return result


def fetch_board_list(param: str, kind: str) -> list[dict]:
    """拉某类（行业/概念）板块名单。param 如 'class_dp'（行业）/'class'（概念）。GBK 编码。"""
    r = requests.get(_SINA_CLASS_URL, params={"param": param}, timeout=10)
    text_ = r.content.decode("gbk", errors="replace")
    m = re.search(r"\{.*\}", text_, re.S)
    data = json.loads(m.group(0)) if m else {}
    rows = []
    for board_code, raw in data.items():
        parts = raw.split(",")
        if board_code and len(parts) > 1 and parts[1]:
            rows.append({"board_code": board_code, "name": parts[1], "kind": kind})
    return rows

_SINA_HIST_URL = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData"


def fetch_index_kline(code: str, datalen: int = 500) -> list[dict]:
    """指数（如 sh000001 上证指数）历史K线，单次 requests 直连，不走 kline.py 那套浏览器反爬流程
    （反爬阈值针对批量个股，单个指数请求不会触发）。失败/无数据返回空列表。
    """
    url = f"{_SINA_HIST_URL}?symbol={code}&scale=240&ma=no&datalen={datalen}"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ 指数K线拉取失败 {code}：{e}")
        return []
    bars = []
    for item in data or []:
        try:
            bars.append({
                "trade_date": item["day"] if "day" in item else item["date"],
                "open": float(item["open"]), "high": float(item["high"]),
                "low": float(item["low"]), "close": float(item["close"]),
                "volume": float(item.get("volume") or 0),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return bars


_SINA_QFQ_URL = "https://finance.sina.com.cn/realstock/company"


def fetch_qfq_factors(code: str, max_retries: int = 3) -> list[dict]:
    """前复权调整因子表：[{"d": "2026-05-25", "f": 1.0}, ...]，按日期倒序，只列出发生过除权
    除息的那些日期（稀疏表）。纯 requests，不用过 kline.py 那套反爬的浏览器流程。
    失败/未上市/没有除权记录一律返回空列表，调用方按"没有因子=不用调整"处理，不抛异常。
    """
    url = f"{_SINA_QFQ_URL}/{sina_symbol(code)}/qfq.js"
    body = ""
    for attempt in range(max_retries):
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            body = r.text
            break
        except Exception as e:  # noqa: BLE001
            if attempt == max_retries - 1:
                print(f"⚠️ 复权因子拉取失败 {code}（已重试{max_retries}次）：{e}")
                return []
            time.sleep(0.5 * (2 ** attempt))
    comment_at = body.find("/*")
    if comment_at >= 0:
        body = body[:comment_at]
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end < start:
        return []
    try:
        parsed = json.loads(body[start:end + 1])
    except ValueError:
        return []
    out = []
    for item in parsed.get("data") or []:
        try:
            out.append({"d": item["d"], "f": float(item["f"])})
        except (KeyError, TypeError, ValueError):
            continue
    return out


_SINA_QUOTE_URL = "https://hq.sinajs.cn/list="


def fetch_realtime_quote(code: str) -> dict | None:
    """单只股票的实时行情（秒级轮询用，走 hq.sinajs.cn，几十毫秒级响应）。

    字段顺序见新浪该接口约定：名称,今开,昨收,最新价,最高,最低,... 第31/32项是日期/时间。
    失败或该代码当天没有行情（未开盘/停牌无数据）返回 None，调用方原样吞掉不抛错。
    """
    symbol = sina_symbol(code)
    try:
        r = requests.get(
            f"{_SINA_QUOTE_URL}{symbol}", timeout=5,
            headers={"Referer": "https://finance.sina.com.cn"},
        )
        r.encoding = "gbk"
        body = r.text
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ 实时行情拉取失败 {code}：{e}")
        return None
    m = re.search(r'"([^"]*)"', body)
    if not m:
        return None
    parts = m.group(1).split(",")
    if len(parts) < 6 or not parts[0]:
        return None
    try:
        return {
            "code": code, "name": parts[0],
            "open": float(parts[1]), "pre_close": float(parts[2]),
            "close": float(parts[3]), "high": float(parts[4]), "low": float(parts[5]),
            "volume": float(parts[8]) if len(parts) > 8 else None,
            "trade_date": parts[30] if len(parts) > 30 else "",
            "time": parts[31] if len(parts) > 31 else "",
        }
    except (ValueError, IndexError):
        return None


def fetch_realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """Fetch several real-time quotes with one Sina request."""
    normalized = list(dict.fromkeys(code.strip() for code in codes if code and code.strip()))
    if not normalized:
        return {}
    symbols = ",".join(sina_symbol(code) for code in normalized)
    try:
        response = requests.get(
            f"{_SINA_QUOTE_URL}{symbols}", timeout=5,
            headers={"Referer": "https://finance.sina.com.cn"},
        )
        response.encoding = "gbk"
        body = response.text
    except Exception as exc:  # noqa: BLE001
        print(f"实时行情批量拉取失败: {exc}")
        return {}

    symbol_to_code = {sina_symbol(code): code for code in normalized}
    result: dict[str, dict] = {}
    for match in re.finditer(r'hq_str_([a-z0-9]+)="([^"]*)"', body, re.IGNORECASE):
        code = symbol_to_code.get(match.group(1).lower())
        parts = match.group(2).split(",")
        if not code or len(parts) < 6 or not parts[0]:
            continue
        try:
            result[code] = {
                "code": code, "name": parts[0],
                "open": float(parts[1]), "pre_close": float(parts[2]),
                "close": float(parts[3]), "high": float(parts[4]), "low": float(parts[5]),
                "volume": float(parts[8]) if len(parts) > 8 else None,
                "trade_date": parts[30] if len(parts) > 30 else "",
                "time": parts[31] if len(parts) > 31 else "",
            }
        except (ValueError, IndexError):
            continue
    return result


_SINA_NEWS_URL = "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php"
_NEWS_ITEM_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})&nbsp;&nbsp;<a target='_blank' href='([^']+)'>([^<]+)</a>"
)


def sina_symbol(code: str) -> str:
    # 已带交易所前缀（指数代码如 sh000001、sz399001）直接返回
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code.startswith(("4", "8")) or code.startswith("92"):
        return "bj" + code
    # 6/9 开头 A 股 + 5 开头上交所 ETF/基金 + 11 开头可转债 → sh
    if code.startswith(("6", "9", "5", "11")):
        return "sh" + code
    return "sz" + code


def fetch_board_members(board_code: str) -> list[str]:
    """拉某板块成分股代码列表，分页拉全量。单页偶发空响应给一次短重试。"""
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


def fetch_stock_news(code: str, days: int = 14, max_pages: int = 5) -> list[dict]:
    """个股相关新闻（新浪个股资讯页），按天数过滤，倒序。失败吞掉返回已拿到部分。"""
    cutoff = date.today() - timedelta(days=days)
    symbol = sina_symbol(code)
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
            break

    items.sort(key=lambda x: (x["date"], x["time"]), reverse=True)
    return items
    result["issuer_name"] = info.get("债券名称")
