"""预计算全市场技术指标/信号（Phase 5）。

数据更新后由 worker 跑一次：拉最近90天历史，对每只股票算 ma_cross / golden_cross 相关标志，
写入 stock_indicator。选股请求随后直接读本表，无需再现算全量历史。计算口径与 services.indicators
完全一致，保证与旧"现算"路径结果一致。
"""
from datetime import date, timedelta

from app.repositories import sync_data as db
from app.services import indicators


def recompute_all() -> int:
    latest_date = db.get_latest_trade_date()
    if not latest_date:
        print("⚠️ 还没有行情快照，无法预计算指标")
        return 0

    since = (date.today() - timedelta(days=90)).isoformat()
    hist = db.get_history_since(since)
    series: dict[str, list[dict]] = {}
    for row in hist:
        series.setdefault(row["code"], []).append(row)

    out: list[dict] = []
    for code, bars in series.items():
        m = indicators.ma_cross_metrics(bars)      # None 时说明数据不足 → 跳过（与现算一致地被排除）
        g = indicators.golden_cross_metrics(bars)
        if m is None and g is None:
            continue
        rec: dict = {"code": code}
        if m is not None:
            price_above20 = m["closes"][-1] > m["ma20"][-1]
            duotou = (
                m["ma5"][-1] is not None and m["ma10"][-1] is not None
                and m["ma5"][-1] > m["ma10"][-1] > m["ma20"][-1]
            )
            rec.update(
                ma5=m["ma5"][-1], ma10=m["ma10"][-1], ma20=m["ma20"][-1],
                cross1=m["cross1_in_3days"], cross23=m["cross23_in_3days"], rise5=m["rise5"],
                price_above20=price_above20, duotou=duotou,
            )
        if g is not None:
            rec.update(macd_recent=g["macd_recent"], kdj_recent=g["kdj_recent"])
        out.append(rec)

    n = db.save_indicators(latest_date, out)
    print(f"✅ 预计算指标完成：{n} 只（交易日 {latest_date}）")
    return n
