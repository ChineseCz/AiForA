"""一次性迁移：把 stock_daily 里已经存在的历史K线（不复权）原地改成前复权。

只在改完 kline.py/sync_data.py 的前复权逻辑那一次跑一遍，把过去攒下的旧数据修正过来；
以后的日常回补由 kline.py 里已经接好的调整逻辑自动保持前复权，不需要重复跑这个脚本
（除非某天怀疑数据又跑偏了，想全量重新对一遍）。

不走浏览器——已经落库的历史直接从 DB 读，只额外拉一次每只股票的复权因子表（纯 requests）。

用法（在 backend/ 目录，用装好 requirements.txt 的环境）：
    python -m scripts.adjust_existing_kline
    python -m scripts.adjust_existing_kline --codes 600519,000001   # 只修指定几只，调试用
"""
import argparse
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app.repositories import sync_data as db  # noqa: E402
from app.services import indicator_precompute  # noqa: E402
from app.services.adjust import compute_qfq  # noqa: E402
from app.services.external.sina import fetch_qfq_factors  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="", help="逗号分隔的股票代码，留空=全市场（按 stock_daily 最新一天的快照枚举）")
    ap.add_argument("--delay", type=float, default=0.2, help="每只股票之间的间隔秒数，别把新浪 qfq.js 打太猛")
    args = ap.parse_args()

    codes = [c.strip() for c in args.codes.split(",") if c.strip()] or \
        [r["code"] for r in db.get_latest_rows() if r.get("code")]
    total = len(codes)
    print(f"共 {total} 只股票，开始逐个拉复权因子并原地修正历史K线…")

    fixed_stocks = 0
    fixed_bars = 0
    no_factor = 0
    for i, code in enumerate(codes, 1):
        bars = db.get_history_for_code(code)
        if not bars:
            continue
        for b in bars:
            b["code"] = code
        try:
            factors = fetch_qfq_factors(code)
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ {code} 复权因子拉取异常：{e}")
            factors = []
        if not factors:
            no_factor += 1
            time.sleep(args.delay)
            continue
        adjusted = compute_qfq(bars, factors)
        db.save_history_bars(adjusted)
        fixed_stocks += 1
        fixed_bars += len(adjusted)
        if i % 50 == 0 or i == total:
            print(f"… {i}/{total}（已修正 {fixed_stocks} 只 / {fixed_bars} 条，{no_factor} 只无复权记录）")
        time.sleep(args.delay)

    print(f"✅ 历史K线复权修正完成：{fixed_stocks} 只 / {fixed_bars} 条被改写，{no_factor} 只无复权记录（原样保留）")
    print("→ 重新预计算指标（MA/MACD/KDJ 依赖的是刚才改过的这批历史数据）…")
    indicator_precompute.recompute_all()


if __name__ == "__main__":
    main()
