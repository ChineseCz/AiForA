"""新浪财经外部数据抓取：板块成分股 + 个股新闻。从旧 stock.py 移植（纯 requests）。

注意 GBK 编码坑：newFLJK/新闻页返回 GBK，需 decode('gbk')。这些在请求期实时抓取，
均为辅助信息，失败吞掉打日志、返回已拿到的部分，不阻塞主流程。
"""
import json
import re
import time
from datetime import date, datetime, timedelta

import requests

_SINA_COUNT_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeStockCount"
_SINA_DATA_URL = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
_SINA_PAGE_SIZE = 80

# 板块分类接口（GBK 编码）
_SINA_CLASS_URL = "http://vip.stock.finance.sina.com.cn/q/view/newFLJK.php"


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_spot_snapshot() -> list[dict]:
    """全市场A股实时快照（逐页拉取约 5000+ 只）。"""
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
            print(f"… 第 {page}/{pages} 页 …")
    return rows


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

_SINA_QFQ_URL = "https://finance.sina.com.cn/realstock/company"


def fetch_qfq_factors(code: str) -> list[dict]:
    """前复权调整因子表：[{"d": "2026-05-25", "f": 1.0}, ...]，按日期倒序，只列出发生过除权
    除息的那些日期（稀疏表）。纯 requests，不用过 kline.py 那套反爬的浏览器流程。
    失败/未上市/没有除权记录一律返回空列表，调用方按"没有因子=不用调整"处理，不抛异常。
    """
    url = f"{_SINA_QFQ_URL}/{sina_symbol(code)}/qfq.js"
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        body = r.text
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ 复权因子拉取失败 {code}：{e}")
        return []
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


_SINA_NEWS_URL = "https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllNewsStock.php"
_NEWS_ITEM_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})&nbsp;(\d{2}:\d{2})&nbsp;&nbsp;<a target='_blank' href='([^']+)'>([^<]+)</a>"
)


def sina_symbol(code: str) -> str:
    if code.startswith(("4", "8")) or code.startswith("92"):
        return "bj" + code
    if code.startswith(("6", "9")):
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
