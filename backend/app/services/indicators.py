"""技术指标与信号序列：从旧 stock.py 逐字移植的纯函数（无 IO）。"""


def moving_avg(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
        else:
            out.append(sum(values[i + 1 - window: i + 1]) / window)
    return out


def crossed_up(fast: list[float | None], slow: list[float | None], t: int) -> bool:
    if fast[t] is None or slow[t] is None or fast[t - 1] is None or slow[t - 1] is None:
        return False
    return fast[t] >= slow[t] and fast[t - 1] < slow[t - 1]


def ema(values: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    out: list[float] = []
    prev = None
    for v in values:
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def compute_macd(closes: list[float]) -> tuple[list[float], list[float], list[float]]:
    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    dif = [a - b for a, b in zip(ema12, ema26)]
    dea = ema(dif, 9)
    macd = [2 * (a - b) for a, b in zip(dif, dea)]
    return dif, dea, macd


def compute_kdj(bars: list[dict]) -> tuple[list[float], list[float], list[float]]:
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    k_list: list[float] = []
    d_list: list[float] = []
    j_list: list[float] = []
    prev_k, prev_d = 50.0, 50.0
    for i in range(len(bars)):
        window_lo = lows[max(0, i - 8): i + 1]
        window_hi = highs[max(0, i - 8): i + 1]
        lo, hi = min(window_lo), max(window_hi)
        rsv = 50.0 if hi == lo else (closes[i] - lo) / (hi - lo) * 100
        k_val = prev_k * 2 / 3 + rsv / 3
        d_val = prev_d * 2 / 3 + k_val / 3
        j_val = 3 * k_val - 2 * d_val
        k_list.append(k_val)
        d_list.append(d_val)
        j_list.append(j_val)
        prev_k, prev_d = k_val, d_val
    return k_list, d_list, j_list


def ma_cross_metrics(bars: list[dict]) -> dict | None:
    """近90天K线 → MA5/10/20 及金叉/5日涨幅指标；数据不足返回 None。"""
    if len(bars) < 23:
        return None
    closes = [b["close"] for b in bars]
    ma5 = moving_avg(closes, 5)
    ma10 = moving_avg(closes, 10)
    ma20 = moving_avg(closes, 20)
    n = len(closes)
    if ma20[-1] is None or n < 6 or closes[-6] in (None, 0):
        return None
    return {
        "closes": closes, "ma5": ma5, "ma10": ma10, "ma20": ma20,
        "cross1_in_3days": any(crossed_up(ma5, ma10, n - 1 - k) for k in range(3) if n - 1 - k >= 1),
        "cross23_in_3days": any(
            crossed_up(ma10, ma20, n - 1 - k) or crossed_up(ma5, ma20, n - 1 - k)
            for k in range(3) if n - 1 - k >= 1
        ),
        "rise5": closes[-1] / closes[-6] - 1 > 0.03,
    }


def golden_cross_metrics(bars: list[dict]) -> dict | None:
    """近4日(含今日) MACD/KDJ 是否各出现过至少一次金叉；数据不足返回 None。"""
    if len(bars) < 23:
        return None
    closes = [b["close"] for b in bars]
    dif, dea, _ = compute_macd(closes)
    k_list, d_list, _ = compute_kdj(bars)
    n = len(closes)
    return {
        "macd_recent": any(crossed_up(dif, dea, n - 1 - i) for i in range(4) if n - 1 - i >= 1),
        "kdj_recent": any(crossed_up(k_list, d_list, n - 1 - i) for i in range(4) if n - 1 - i >= 1),
    }


def daily_signal_series(bars: list[dict]) -> tuple[list[bool], list[bool]]:
    closes = [b["close"] for b in bars]
    n = len(closes)
    ma5 = moving_avg(closes, 5)
    ma10 = moving_avg(closes, 10)
    ma20 = moving_avg(closes, 20)
    strict_ok = [False] * n
    loose_ok = [False] * n
    for t in range(n):
        if ma20[t] is None or t < 5 or closes[t - 5] in (None, 0):
            continue
        cross1 = any(crossed_up(ma5, ma10, t - k) for k in range(3) if t - k >= 1)
        cross23 = any(
            crossed_up(ma10, ma20, t - k) or crossed_up(ma5, ma20, t - k)
            for k in range(3) if t - k >= 1
        )
        rise5 = closes[t] / closes[t - 5] - 1 > 0.03
        loose_ok[t] = bool(cross1 and cross23 and rise5)
        if loose_ok[t]:
            price_above20 = closes[t] > ma20[t]
            duotou = ma5[t] is not None and ma10[t] is not None and ma5[t] > ma10[t] > ma20[t]
            strict_ok[t] = bool(price_above20 and duotou)
    return strict_ok, loose_ok


def daily_sell_signal_series(closes: list[float], ma5: list[float | None], ma10: list[float | None],
                             dif: list[float], dea: list[float]) -> tuple[list[bool], list[bool]]:
    n = len(closes)
    mid_reverse_ok = [False] * n
    stop_loss_ok = [False] * n
    for t in range(1, n):
        trend_break = (
            ma5[t] is not None and ma10[t] is not None and ma5[t - 1] is not None and ma10[t - 1] is not None
            and ma5[t] < ma10[t] and ma5[t - 1] >= ma10[t - 1]
        )
        macd_dead = dif[t] < dea[t] and dif[t - 1] >= dea[t - 1]
        mid_reverse_ok[t] = bool(trend_break or macd_dead)
        stop_loss_ok[t] = bool(
            ma5[t] is not None and ma5[t - 1] is not None
            and closes[t] < ma5[t] and closes[t - 1] >= ma5[t - 1]
        )
    return mid_reverse_ok, stop_loss_ok


def daily_golden_signal_series(dif: list[float], dea: list[float],
                               k_list: list[float], d_list: list[float]) -> list[bool]:
    n = len(dif)
    out = [False] * n
    for t in range(n):
        macd_recent = any(crossed_up(dif, dea, t - i) for i in range(4) if t - i >= 1)
        kdj_recent = any(crossed_up(k_list, d_list, t - i) for i in range(4) if t - i >= 1)
        out[t] = bool(macd_recent and kdj_recent)
    return out
