"""东方财富财务指标抓取：全市场最新一期业绩报表（EPS/ROE/净利润同比/营收同比/毛利率）。

从旧 stock.py 移植（纯 requests，带 Referer 头，实测稳定）。
"""
import requests

_EM_FINANCE_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
_EM_FINANCE_REPORT = "RPT_LICO_FN_CPD"
_EM_FINANCE_COLUMNS = "SECURITY_CODE,SECURITY_NAME_ABBR,SECUCODE,REPORTDATE,BASIC_EPS,WEIGHTAVG_ROE,YSTZ,SJLTZ,XSMLL"
_EM_FINANCE_PAGE_SIZE = 500
_EM_HEADERS = {"Referer": "https://data.eastmoney.com/"}


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


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
