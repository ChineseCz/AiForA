"""数据同步编排（requests 型，可容器化）：快照 / 财务 / 板块名单 / 板块成分股全量。

从旧 stock.py 的 sync_* 函数移植：拉取 + 落库。由 Phase 2 的 Celery 容器化 worker 调用。
K线回补（backfill）依赖真实浏览器，不在此文件，见 scrapers/kline.py（宿主 worker）。
"""
from datetime import date

from app.repositories import sync_data as db
from app.services import matching
from app.services.external import eastmoney, sina


def sync_daily_snapshot() -> int:
    print("… 拉取全市场行情快照 …")
    rows = sina.fetch_spot_snapshot()
    trade_date = date.today().isoformat()
    n = db.save_snapshot(trade_date, rows)
    print(f"✅ 已写入 {n} 条快照（{trade_date}）")
    return n


def sync_finance_snapshot() -> int:
    print("… 拉取全市场最新财报指标 …")
    rows = eastmoney.fetch_finance_snapshot()
    n = db.save_finance(rows)
    print(f"✅ 已写入 {n} 条财务指标（报告期 {rows[0]['report_date'] if rows else '-'}）")
    return n


def sync_sector_catalog() -> int:
    """行业名录走 save_sector_catalog（追加式，与雪球申万行业共享撞名跳过逻辑）；
    概念名录走 replace_concept_catalog（整体替换旧 gn_ 概念板块，见该函数说明）。
    """
    industry_rows = sina.fetch_board_list("class_dp", "industry")
    n_industry = db.save_sector_catalog(industry_rows)
    concept_rows = sina.fetch_hot_concepts()
    n_concept = db.replace_concept_catalog(concept_rows)
    print(f"✅ 已同步 {n_industry} 个行业板块 + {n_concept} 个概念板块")
    return n_industry + n_concept


def sync_all_sector_members() -> int:
    """全量同步所有板块成分股。个别板块偶发失败跳过并继续（沿用旧 per-item 容错）。"""
    catalog = db.get_sector_catalog()
    if not catalog:
        raise ValueError("还没有板块名单，请先运行板块名单同步")
    total = len(catalog)
    n_codes = 0
    n_failed = 0
    for i, sec in enumerate(catalog, 1):
        try:
            codes = matching.get_sector_members(sec["name"])
            n_codes += len(codes)
        except Exception as e:  # noqa: BLE001
            n_failed += 1
            print(f"⚠️ 板块「{sec['name']}」同步失败，跳过：{e}")
        if i % 20 == 0 or i == total:
            print(f"… 已同步 {i}/{total} 个板块的成分股 …")
    print(f"✅ 板块成分股全量同步完成：{total} 个板块（失败 {n_failed} 个），共 {n_codes} 条关系")
    return total
