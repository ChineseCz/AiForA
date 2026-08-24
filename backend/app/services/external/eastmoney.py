"""东方财富财务指标抓取：全市场最新一期业绩报表（EPS/ROE/净利润同比/营收同比/毛利率）。

从旧 stock.py 移植（纯 requests，带 Referer 头，实测稳定）。
"""
import requests

_EM_FINANCE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_FINANCE_REPORT = "RPT_LICO_FN_CPD"
_EM_FINANCE_COLUMNS = "SECURITY_CODE,SECURITY_NAME_ABBR,SECUCODE,REPORTDATE,BASIC_EPS,WEIGHTAVG_ROE,YSTZ,SJLTZ,XSMLL"
_EM_FINANCE_PAGE_SIZE = 500
_EM_HEADERS = {"Referer": "https://data.eastmoney.com/"}
_EM_BOND_URL = "https://push2.eastmoney.com/api/qt/clist/get"
_EM_BOND_FIELDS = "f2,f3,f4,f5,f6,f12,f13,f14,f15,f16,f17,f18"
_EM_BOND_PAGE_SIZE = 100


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


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
