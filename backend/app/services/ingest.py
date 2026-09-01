"""数据同步编排（requests 型，可容器化）：快照 / 财务 / 板块名单 / 板块成分股全量。

从旧 stock.py 的 sync_* 函数移植：拉取 + 落库。由 Phase 2 的 Celery 容器化 worker 调用。
K线回补（backfill）依赖真实浏览器，不在此文件，见 scrapers/kline.py（宿主 worker）。
"""
from datetime import date
import re

from app.repositories import sync_data as db
from app.services import matching
from app.services.external import eastmoney, sina


def sync_index_benchmarks() -> int:
    """Sync benchmark indexes used by article performance review."""
    benchmarks = (("sh000300", "沪深300"),)
    total = 0
    for code, name in benchmarks:
        # 新浪该接口对指数的单次返回上限约为 500，超过后可能直接返回空。
        rows = sina.fetch_index_kline(code, datalen=500)
        total += db.save_index_daily(code, name, rows)
        print(f"指数 {name}：写入 {len(rows)} 条")
    return total


def sync_daily_snapshot() -> int:
    """同步 A股 + ETF + 可转债行情快照。"""
    print("… 拉取全市场行情快照（A股 + ETF + 可转债）…")
    trade_date = date.today().isoformat()

    # A股快照
    print("  → 拉取 A股 …")
    stock_rows = sina.fetch_spot_snapshot()
    n_stock = db.save_snapshot(trade_date, stock_rows)
    print(f"  ✅ A股：{n_stock} 条")

    # ETF 快照
    print("  → 拉取 ETF …")
    etf_rows = sina.fetch_etf_snapshot()
    n_etf = db.save_snapshot(trade_date, etf_rows)
    print(f"  ✅ ETF：{n_etf} 条")

    # 可转债使用独立行情源和数据表，但归入同一轮全市场同步
    print("  → 拉取可转债 …")
    bond_rows = sina.fetch_bond_snapshot()
    n_bond = db.save_bond_snapshot(trade_date, bond_rows)
    print(f"  ✅ 可转债：{n_bond} 条")

    total = n_stock + n_etf + n_bond
    print(f"✅ 已写入 {total} 条快照（A股 {n_stock} + ETF {n_etf} + 可转债 {n_bond}，{trade_date}）")
    return total


def sync_finance_snapshot() -> int:
    print("… 拉取全市场最新财报指标 …")
    rows = eastmoney.fetch_finance_snapshot()
    n = db.save_finance(rows)
    print(f"✅ 已写入 {n} 条财务指标（报告期 {rows[0]['report_date'] if rows else '-'}）")
    return n


def sync_bond_snapshot() -> int:
    print("… 拉取全市场可转债行情 …")
    rows = sina.fetch_bond_snapshot()
    n = db.save_bond_snapshot(date.today().isoformat(), rows)
    print(f"✅ 已写入 {n} 条可转债行情")
    return n


def sync_bond_basic() -> int:
    """同步最新交易日的可转债转股价、到期日和信用等级。"""
    rows = db.get_latest_bond_rows(limit=5000)
    if not rows:
        return 0
    print(f"… 同步 {len(rows)} 只可转债基础资料 …")
    stock_rows = db.get_latest_rows()
    basic = []
    stock_names = [(r.get("code"), r.get("name"), r.get("close")) for r in stock_rows if r.get("code") and r.get("name")]

    def normalize(value: str) -> str:
        return re.sub(r"(股份有限公司|有限公司|集团|公司|证券|银行|转债|转[0-9一二三四五六七八九十]+)$", "", value).strip()

    def match_stock(bond_name: str) -> tuple[str | None, str | None, float | None]:
        key = normalize(bond_name)
        candidates = [r for r in stock_names if key and (key in normalize(str(r[1])) or normalize(str(r[1])) in key)]
        if len(candidates) == 1:
            return candidates[0]
        return None, None, None

    def fetch_one(row: dict) -> dict:
        item = sina.fetch_bond_basic(row["code"])
        stock_code, stock_name, stock_close = match_stock(str(row.get("name") or item.get("issuer_name") or ""))
        convert_price = item.get("convert_price")
        close = row.get("close")
        conversion_value = None
        premium_rate = None
        if stock_close and convert_price and convert_price > 0:
            conversion_value = stock_close * 100 / convert_price
            if close and conversion_value:
                premium_rate = (close / conversion_value - 1) * 100
        item.update({
            "stock_code": stock_code, "stock_name": stock_name,
            "conversion_value": conversion_value, "premium_rate": premium_rate,
        })
        return item

    import concurrent.futures
    updated = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_one, row): row["code"] for row in rows}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            code = futures[future]
            try:
                basic.append(future.result())
            except Exception as e:  # noqa: BLE001
                print(f"⚠️ 转债资料拉取失败 {code}：{e}")
            if len(basic) >= 20 or i == len(futures):
                updated += db.update_bond_basic(basic)
                basic = []
            if i % 25 == 0 or i == len(futures):
                print(f"… 已处理 {i}/{len(futures)} 只 …")
    n = updated
    print(f"✅ 已更新 {n} 只可转债基础资料")
    return n


def sync_sector_catalog() -> int:
    """行业名录走 save_sector_catalog（追加式，与雪球申万行业共享撞名跳过逻辑）；
    概念名录走 replace_concept_catalog（整体替换旧 gn_ 概念板块，见该函数说明）。
    """
    industry_rows = sina.fetch_board_list("class_dp", "industry")
    n_industry = db.save_sector_catalog(industry_rows)
    concept_rows = sina.fetch_hot_concepts()
    n_concept = db.replace_concept_catalog(concept_rows)
    parts = []
    if n_industry:
        parts.append(f"{n_industry} 个行业板块")
    if n_concept:
        parts.append(f"{n_concept} 个概念板块")
    print(f"✅ 已同步 {' + '.join(parts) if parts else '0 条板块'}")
    return n_industry + n_concept


def sync_all_sector_members() -> int:
    """全量同步所有板块成分股（并发拉取新浪接口）。个别板块偶发失败跳过并继续（沿用旧 per-item 容错）。"""
    import concurrent.futures

    catalog = db.get_sector_catalog()
    if not catalog:
        raise ValueError("还没有板块名单，请先运行板块名单同步")

    # 过滤掉雪球板块（需浏览器，单独任务处理）
    sina_sectors = [s for s in catalog if not s["board_code"].startswith("xq_")]
    xq_count = len(catalog) - len(sina_sectors)

    total = len(sina_sectors)
    n_codes = 0
    n_failed = 0
    completed = 0

    def fetch_one(sec: dict) -> tuple[str, list[str]] | None:
        """返回 (sector_name, codes) 或 None"""
        try:
            codes = matching.get_sector_members(sec["name"])
            return (sec["name"], codes)
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 板块「{sec['name']}」同步失败：{e}")
            return None

    # 并发拉取（限制10并发，避免打爆上游）
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_one, sec) for sec in sina_sectors]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                n_codes += len(result[1])
            else:
                n_failed += 1
            completed += 1
            if completed % 50 == 0 or completed == total:
                print(f"… 已同步 {completed}/{total} 个板块的成分股 …")

    msg_parts = [f"{total}个新浪板块（失败{n_failed}个）", f"共{n_codes}条关系"]
    if xq_count:
        msg_parts.insert(0, f"跳过{xq_count}个雪球板块")
    print(f"✅ 板块成分股全量同步完成：{' / '.join(msg_parts)}")
    return total
