"""前复权价格调整：把新浪 qfq.js 那张稀疏的"除权日 -> 累计因子"表应用到原始 OHLC 上。

算法（对拍过新浪自己给的青山纸业例子，见 doc）：某天的原始价，除以"事件日期 <= 该天"里
最新一条的 f 值，就是前复权价。factors 按日期倒序传入最自然（qfq.js 本身就是倒序），
这里用二分找第一个 <= trade_date 的事件，不要求调用方预先排序。
"""
import bisect


def _adjustment_for(trade_date: str, sorted_dates: list[str], sorted_factors: list[float]) -> float:
    """sorted_dates/sorted_factors 按日期升序；返回 <= trade_date 的最新一条对应的 factor，
    没有更早的事件（trade_date 早于所有除权日）就用最早那条——比如 qfq.js 兜底的 1900-01-01。
    """
    idx = bisect.bisect_right(sorted_dates, trade_date) - 1
    if idx < 0:
        idx = 0
    return sorted_factors[idx]


def compute_qfq(bars: list[dict], factors: list[dict]) -> list[dict]:
    """bars: [{"trade_date","open","high","low","close",...}, ...]（其它字段原样保留，包括 volume）。
    factors: sina.fetch_qfq_factors() 的返回值，顺序无要求。
    没有任何除权记录（factors 为空）时原样返回，不做无意义的复制。
    """
    if not factors or not bars:
        return bars
    ordered = sorted(factors, key=lambda f: f["d"])
    sorted_dates = [f["d"] for f in ordered]
    sorted_factors = [f["f"] for f in ordered]

    out = []
    for bar in bars:
        trade_date = bar.get("trade_date")
        factor = _adjustment_for(trade_date, sorted_dates, sorted_factors) if trade_date else 1.0
        adjusted = dict(bar)
        if factor and factor != 1.0:
            for key in ("open", "high", "low", "close"):
                v = bar.get(key)
                if v is not None:
                    adjusted[key] = v / factor
        out.append(adjusted)
    return out
