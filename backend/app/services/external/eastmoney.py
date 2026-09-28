"""东方财富财务指标和按需行情数据抓取。

从旧 stock.py 移植（纯 requests，带 Referer 头，实测稳定）。
"""
from datetime import date, timedelta
from urllib.parse import quote

import requests

_EM_FINANCE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_FINANCE_REPORT = "RPT_LICO_FN_CPD"
_EM_FINANCE_COLUMNS = "SECURITY_CODE,SECURITY_NAME_ABBR,SECUCODE,REPORTDATE,BASIC_EPS,WEIGHTAVG_ROE,YSTZ,SJLTZ,XSMLL"
_EM_FINANCE_PAGE_SIZE = 500
_EM_HEADERS = {"Referer": "https://data.eastmoney.com/"}
_EM_MINUTE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_EM_BOND_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_EM_BOND_FIELDS = "f2,f3,f4,f5,f6,f12,f13,f14,f15,f16,f17,f18"
_EM_BOND_PAGE_SIZE = 100


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _em_market(code: str) -> int:
    """东方财富市场编号：1=沪市，0=深市。"""
    return 1 if code.startswith(("5", "6", "9", "11", "12")) else 0


def fetch_intraday(code: str, day: str) -> dict:
    """按需获取指定交易日 1 分钟线，不落库。"""
    target = date.fromisoformat(day)
    end = target + timedelta(days=1)
    # 东方财富 1 分钟接口对历史日期可能忽略 beg/end 并返回当天数据。
    # 历史日期切换为 5 分钟，保证日期选择器请求的日期与返回数据一致。
    klt = "1" if target == date.today() else "5"
    response = requests.get(
        _EM_MINUTE_URL,
        params={
            "secid": f"{_em_market(code)}.{code}",
            "klt": klt, "fqt": "0",
            "beg": target.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"),
            "lmt": "10000",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        },
        headers={**_EM_HEADERS, "User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    data = (response.json().get("data") or {})
    bars = []
    for raw in data.get("klines") or []:
        parts = raw.split(",")
        if len(parts) < 7:
            continue
        if not parts[0].startswith(day):
            continue
        bars.append({
            "time": parts[0],
            "open": _to_float(parts[1]), "close": _to_float(parts[2]),
            "high": _to_float(parts[3]), "low": _to_float(parts[4]),
            "volume": _to_float(parts[5]) or 0, "amount": _to_float(parts[6]) or 0,
        })
    return {
        "code": code, "name": data.get("name") or code, "date": day,
        "pre_close": _to_float(data.get("preKPrice")), "bars": bars,
    }


def fetch_bond_snapshot() -> list[dict]:
    """抓取沪深可转债行情快照。

    东方财富的列表接口提供稳定的市场快照字段；转股价、溢价率等发行条款
    字段先保留为空，后续再接入转债资料接口补齐，避免影响首版行情上线。
    """
    rows: list[dict] = []
    page = 1
    pages = 1
    while page <= pages:
        r = requests.get(
            _EM_BOND_URL,
            params={
                "pn": page, "pz": _EM_BOND_PAGE_SIZE, "po": 1, "np": 1,
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "fltt": 2, "invt": 2, "fid": "f3",
                "fs": "b:MK0354", "fields": _EM_BOND_FIELDS,
            },
            headers=_EM_HEADERS,
            timeout=15,
        )
        result = r.json().get("data") or {}
        diff = result.get("diff") or []
        total = int(result.get("total") or len(diff) or 0)
        pages = max(1, (total + _EM_BOND_PAGE_SIZE - 1) // _EM_BOND_PAGE_SIZE)
        for it in diff:
            code = str(it.get("f12") or "").zfill(6)
            if not code or code == "000000":
                continue
            rows.append({
                "code": code, "name": it.get("f14"),
                "close": _to_float(it.get("f2")), "change_pct": _to_float(it.get("f3")),
                "volume": _to_float(it.get("f5")), "amount": _to_float(it.get("f6")),
                "high": _to_float(it.get("f15")), "low": _to_float(it.get("f16")),
                "open": _to_float(it.get("f17")), "pre_close": _to_float(it.get("f18")),
                "stock_code": None, "stock_name": None, "convert_price": None,
                "conversion_value": None, "premium_rate": None, "maturity_date": None,
                "rating": None, "redeem_status": None,
            })
        if page % 2 == 0 or page == pages:
            print(f"… 可转债第 {page}/{pages} 页 …")
        page += 1
    return rows


def _latest_finance_report_date() -> str:
    """用当前数据里最新的 REPORTDATE，进入下一报告期后无需改代码。"""
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
    """全市场最新一期财务指标快照（逐页拉取）。"""
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
                continue
            rows.append({
                "code": it.get("SECURITY_CODE"), "name": it.get("SECURITY_NAME_ABBR"),
                "report_date": report_date, "eps": _to_float(it.get("BASIC_EPS")),
                "roe": _to_float(it.get("WEIGHTAVG_ROE")), "net_profit_yoy": _to_float(it.get("SJLTZ")),
                "revenue_yoy": _to_float(it.get("YSTZ")), "gross_margin": _to_float(it.get("XSMLL")),
            })
        if page % 5 == 0 or page == pages:
            print(f"… 第 {page}/{pages} 页 …")
        page += 1
    return rows


_EM_HOLDERS_REPORT = "RPT_F10_EH_HOLDERS"
NATIONAL_TEAM_INSTITUTIONS = (
    "中央汇金投资有限责任公司",
    "中央汇金资产管理有限责任公司",
    "中国证券金融股份有限公司",
    "全国社会保障基金理事会",
)


def fetch_national_team_holdings() -> list[dict]:
    """拉取国家队机构的历史十大股东披露。

    东方财富接口支持精确 HOLDER_NAME 查询，不依赖逐股网页抓取。返回原始的
    报告期末持仓记录；调用方负责计算“退出”等跨报告期状态。
    """
    columns = (
        "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,END_DATE,HOLDER_NAME,"
        "HOLD_NUM,HOLD_NUM_RATIO,HOLD_NUM_CHANGE,HOLD_RATIO_QOQ,HOLDER_MARKET_CAP"
    )
    rows: list[dict] = []
    for institution in NATIONAL_TEAM_INSTITUTIONS:
        page = 1
        while True:
            params = {
                "reportName": _EM_HOLDERS_REPORT,
                "columns": columns,
                "filter": f'(HOLDER_NAME="{institution}")',
                "pageNumber": str(page), "pageSize": "500",
                "sortColumns": "END_DATE,SECURITY_CODE", "sortTypes": "-1,1",
            }
            response = requests.get(_EM_FINANCE_URL, params=params, headers=_EM_HEADERS, timeout=20)
            response.raise_for_status()
            result = response.json().get("result") or {}
            data = result.get("data") or []
            for item in data:
                end_date = str(item.get("END_DATE") or "")[:10]
                code = str(item.get("SECURITY_CODE") or "").zfill(6)
                if not end_date or not code:
                    continue
                raw_change = item.get("HOLD_NUM_CHANGE")
                change_shares = None
                change_type = raw_change if isinstance(raw_change, str) and not _to_float(raw_change) else None
                if _to_float(raw_change) is not None:
                    change_shares = _to_float(raw_change)
                    change_type = "增持" if change_shares > 0 else "减持" if change_shares < 0 else "不变"
                rows.append({
                    "report_date": end_date, "institution": institution, "code": code,
                    "name": item.get("SECURITY_NAME_ABBR"),
                    "shares": _to_float(item.get("HOLD_NUM")),
                    "holding_ratio": _to_float(item.get("HOLD_NUM_RATIO")),
                    "change_shares": change_shares, "change_type": change_type,
                    "market_value": _to_float(item.get("HOLDER_MARKET_CAP")),
                    "source": "eastmoney",
                })
            pages = int(result.get("pages") or page)
            if page >= pages or not data:
                break
            page += 1
    return rows
