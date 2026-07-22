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


def compute_macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9,
) -> tuple[list[float], list[float], list[float]]:
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    dif = [a - b for a, b in zip(ema_fast, ema_slow)]
    dea = ema(dif, signal)
    macd = [2 * (a - b) for a, b in zip(dif, dea)]
    return dif, dea, macd


def compute_kdj(bars: list[dict], window: int = 9) -> tuple[list[float], list[float], list[float]]:
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    closes = [b["close"] for b in bars]
    offset = window - 1
    k_list: list[float] = []
    d_list: list[float] = []
    j_list: list[float] = []
    prev_k, prev_d = 50.0, 50.0
    for i in range(len(bars)):
        window_lo = lows[max(0, i - offset): i + 1]
        window_hi = highs[max(0, i - offset): i + 1]
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


def compute_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    """标准 Wilder RSI：前 period 根返回 None（无足够数据），此后按平滑平均涨跌幅计算。"""
    n = len(closes)
    out: list[float | None] = [None] * n
    if n <= period:
        return out
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, n)]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, n)]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        idx = i + 1  # gains[i] 对应 closes[i+1] 相对 closes[i] 的涨跌
        out[idx] = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return out


def compute_boll(
    closes: list[float], period: int = 20, mult: float = 2.0,
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """布林带 mid/upper/lower，及带宽（upper-lower）/mid 供收口判断。"""
    mid = moving_avg(closes, period)
    upper: list[float | None] = [None] * len(closes)
    lower: list[float | None] = [None] * len(closes)
    for i in range(len(closes)):
        if mid[i] is None:
            continue
        window = closes[i + 1 - period: i + 1]
        m = mid[i]
        variance = sum((v - m) ** 2 for v in window) / period
        std = variance ** 0.5
        upper[i] = m + mult * std
        lower[i] = m - mult * std
    return mid, upper, lower


def ma_cross_metrics(
    bars: list[dict],
    ma_fast: int = 5, ma_mid: int = 10, ma_slow: int = 20,
    cross_days: int = 3, rise_days: int = 5, rise_pct: float = 0.03,
) -> dict | None:
    """近90天K线 → MA快/中/慢 及金叉/N日涨幅指标；数据不足返回 None。

    参数默认值＝原硬编码值（5/10/20、3日回望、5日涨幅>3%），不传参时行为与旧版完全一致。
    """
    min_len = max(ma_slow, rise_days) + 3
    if len(bars) < min_len:
        return None
    closes = [b["close"] for b in bars]
    ma5 = moving_avg(closes, ma_fast)
    ma10 = moving_avg(closes, ma_mid)
    ma20 = moving_avg(closes, ma_slow)
    n = len(closes)
    if ma20[-1] is None or n < rise_days + 1 or closes[-rise_days - 1] in (None, 0):
        return None
    return {
        "closes": closes, "ma5": ma5, "ma10": ma10, "ma20": ma20,
        "cross1_in_3days": any(crossed_up(ma5, ma10, n - 1 - k) for k in range(cross_days) if n - 1 - k >= 1),
        "cross23_in_3days": any(
            crossed_up(ma10, ma20, n - 1 - k) or crossed_up(ma5, ma20, n - 1 - k)
            for k in range(cross_days) if n - 1 - k >= 1
        ),
        "rise5": closes[-1] / closes[-rise_days - 1] - 1 > rise_pct,
    }


def golden_cross_metrics(
    bars: list[dict],
    macd_fast: int = 12, macd_slow: int = 26, macd_signal: int = 9,
    kdj_window: int = 9, cross_days: int = 4,
) -> dict | None:
    """近N日(含今日) MACD/KDJ 是否各出现过至少一次金叉；数据不足返回 None。

    参数默认值＝原硬编码值（12/26/9 EMA、9日KDJ窗口、4日回望），不传参时行为与旧版完全一致。
    """
    min_len = max(23, macd_slow + macd_signal, kdj_window) + cross_days
    if len(bars) < min_len:
        return None
    closes = [b["close"] for b in bars]
    dif, dea, _ = compute_macd(closes, macd_fast, macd_slow, macd_signal)
    k_list, d_list, _ = compute_kdj(bars, kdj_window)
    n = len(closes)
    return {
        "macd_recent": any(crossed_up(dif, dea, n - 1 - i) for i in range(cross_days) if n - 1 - i >= 1),
        "kdj_recent": any(crossed_up(k_list, d_list, n - 1 - i) for i in range(cross_days) if n - 1 - i >= 1),
    }


def daily_signal_series(
    bars: list[dict], cross_days: int = 3, rise_days: int = 5, rise_pct: float = 0.03,
) -> tuple[list[bool], list[bool]]:
    closes = [b["close"] for b in bars]
    n = len(closes)
    ma5 = moving_avg(closes, 5)
    ma10 = moving_avg(closes, 10)
    ma20 = moving_avg(closes, 20)
    strict_ok = [False] * n
    loose_ok = [False] * n
    for t in range(n):
        if ma20[t] is None or t < rise_days or closes[t - rise_days] in (None, 0):
            continue
        cross1 = any(crossed_up(ma5, ma10, t - k) for k in range(cross_days) if t - k >= 1)
        cross23 = any(
            crossed_up(ma10, ma20, t - k) or crossed_up(ma5, ma20, t - k)
            for k in range(cross_days) if t - k >= 1
        )
        rise_ok = closes[t] / closes[t - rise_days] - 1 > rise_pct
        loose_ok[t] = bool(cross1 and cross23 and rise_ok)
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


def volume_breakout_metrics(bars: list[dict], breakout_days: int = 20, volume_mult: float = 1.5) -> dict | None:
    """今日收盘突破前 breakout_days 日最高价，且今日成交量 > 前 breakout_days 日均量 × volume_mult。"""
    if len(bars) < breakout_days + 1:
        return None
    window = bars[-1 - breakout_days: -1]
    today = bars[-1]
    prior_high = max(b["high"] for b in window)
    avg_vol = sum(b["volume"] for b in window) / len(window)
    return {"breakout": bool(today["close"] > prior_high and avg_vol > 0 and today["volume"] > avg_vol * volume_mult)}


def pullback_low_volume_metrics(
    bars: list[dict],
    lookback_days: int = 10, ma_period: int = 20, near_pct: float = 0.02,
    recent_days: int = 3, avg_days: int = 20, spike_mult: float = 1.5, low_volume_mult: float = 0.7,
) -> dict | None:
    """近 lookback_days 日内曾放量上涨，现价回踩 MA 附近，近期量能明显低于均量。"""
    min_len = max(lookback_days, avg_days) + recent_days + 1
    if len(bars) < min_len:
        return None
    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]
    ma = moving_avg(closes, ma_period)
    n = len(bars)
    if ma[-1] is None or not ma[-1]:
        return None

    had_spike_rise = False
    for t in range(n - lookback_days, n):
        if t < 1 or t - avg_days < 0:
            continue
        base_avg = sum(volumes[t - avg_days: t]) / avg_days
        if base_avg > 0 and volumes[t] > base_avg * spike_mult and closes[t] > closes[t - 1]:
            had_spike_rise = True
            break

    near_ma = abs(closes[-1] / ma[-1] - 1) <= near_pct
    recent_avg_vol = sum(volumes[-recent_days:]) / recent_days
    base_avg_vol = sum(volumes[-avg_days:]) / avg_days
    low_volume = bool(base_avg_vol > 0 and recent_avg_vol < base_avg_vol * low_volume_mult)

    return {"had_spike_rise": had_spike_rise, "near_ma": near_ma, "low_volume": low_volume}


def boll_squeeze_breakout_metrics(
    bars: list[dict], period: int = 20, mult: float = 2.0, squeeze_days: int = 60, squeeze_pct: float = 0.3,
) -> dict | None:
    """近 squeeze_days 日内带宽处于低位（收口），今日收盘上穿布林带上轨。"""
    min_len = period + squeeze_days
    if len(bars) < min_len:
        return None
    closes = [b["close"] for b in bars]
    mid, upper, lower = compute_boll(closes, period, mult)
    n = len(closes)
    if upper[-1] is None or upper[-2] is None or mid[-1] in (None, 0) or mid[-2] in (None, 0):
        return None

    widths: list[float] = []
    for i in range(n - squeeze_days, n):
        if upper[i] is None or lower[i] is None or not mid[i]:
            continue
        widths.append((upper[i] - lower[i]) / mid[i])
    if len(widths) < squeeze_days // 2:
        return None
    yesterday_width = (upper[-2] - lower[-2]) / mid[-2]
    rank = sum(1 for w in widths if w <= yesterday_width) / len(widths)
    squeezed = rank <= squeeze_pct

    breakout = closes[-1] > upper[-1] and closes[-2] <= upper[-2]
    return {"squeezed": squeezed, "breakout": breakout}


def rsi_bounce_metrics(bars: list[dict], period: int = 14, threshold: float = 30.0, lookback_days: int = 2) -> dict | None:
    """近 lookback_days 日内 RSI 由 <threshold 回升到 >=threshold（金叉阈值线），且今日收阳。"""
    if len(bars) < period + lookback_days + 1:
        return None
    closes = [b["close"] for b in bars]
    rsi = compute_rsi(closes, period)
    n = len(closes)
    bounced = False
    for k in range(lookback_days):
        t = n - 1 - k
        if t < 1 or rsi[t] is None or rsi[t - 1] is None:
            continue
        if rsi[t] >= threshold and rsi[t - 1] < threshold:
            bounced = True
            break
    bullish_today = bars[-1]["close"] > bars[-1]["open"]
    return {"bounced": bounced, "bullish_today": bullish_today}


def volume_price_up_metrics(bars: list[dict], streak_days: int = 3) -> dict | None:
    """连续 streak_days 日成交量递增且收盘价递增（含今日）。"""
    if len(bars) < streak_days + 1:
        return None
    closes = [b["close"] for b in bars]
    volumes = [b["volume"] for b in bars]
    n = len(closes)
    streak_ok = all(
        closes[n - i] > closes[n - i - 1] and volumes[n - i] > volumes[n - i - 1]
        for i in range(1, streak_days + 1)
    )
    return {"streak_ok": streak_ok}


def daily_golden_signal_series(
    dif: list[float], dea: list[float], k_list: list[float], d_list: list[float],
    cross_days: int = 4, require_both: bool = True,
) -> list[bool]:
    n = len(dif)
    out = [False] * n
    for t in range(n):
        macd_recent = any(crossed_up(dif, dea, t - i) for i in range(cross_days) if t - i >= 1)
        kdj_recent = any(crossed_up(k_list, d_list, t - i) for i in range(cross_days) if t - i >= 1)
        out[t] = bool(macd_recent and kdj_recent) if require_both else bool(macd_recent or kdj_recent)
    return out


def daily_volume_breakout_series(bars: list[dict], breakout_days: int = 20, volume_mult: float = 1.5) -> list[bool]:
    """逐日放量突破信号：收盘突破前N日最高价 且 当日量>前N日均量×倍数。"""
    n = len(bars)
    out = [False] * n
    for i in range(breakout_days, n):
        window = bars[i - breakout_days: i]
        b = bars[i]
        prior_high = max(w["high"] for w in window)
        avg_vol = sum(w["volume"] for w in window) / len(window)
        out[i] = bool(b["close"] > prior_high and avg_vol > 0 and b["volume"] > avg_vol * volume_mult)
    return out


def daily_boll_breakout_series(bars: list[dict], period: int = 20, mult: float = 2.0) -> list[bool]:
    """逐日布林带上轨突破信号：昨收≤上轨，今收>上轨。"""
    closes = [b["close"] for b in bars]
    _, upper, _ = compute_boll(closes, period, mult)
    n = len(closes)
    out = [False] * n
    for i in range(1, n):
        if upper[i] is None or upper[i - 1] is None:
            continue
        out[i] = bool(closes[i] > upper[i] and closes[i - 1] <= upper[i - 1])
    return out


def daily_rsi_bounce_series(bars: list[dict], period: int = 14, threshold: float = 30.0) -> list[bool]:
    """逐日RSI超卖反弹信号：RSI从<threshold 回升到 >=threshold 且当日收阳。"""
    closes = [b["close"] for b in bars]
    rsi = compute_rsi(closes, period)
    n = len(closes)
    out = [False] * n
    for i in range(1, n):
        if rsi[i] is None or rsi[i - 1] is None:
            continue
        if rsi[i] >= threshold and rsi[i - 1] < threshold and bars[i]["close"] > bars[i]["open"]:
            out[i] = True
    return out


def daily_rsi_overbought_series(bars: list[dict], period: int = 14, threshold: float = 70.0) -> list[bool]:
    """逐日RSI超买回落信号：RSI从>threshold 回落到 <=threshold。"""
    closes = [b["close"] for b in bars]
    rsi = compute_rsi(closes, period)
    n = len(closes)
    out = [False] * n
    for i in range(1, n):
        if rsi[i] is None or rsi[i - 1] is None:
            continue
        if rsi[i] <= threshold and rsi[i - 1] > threshold:
            out[i] = True
    return out


def daily_break_ma_series(bars: list[dict], period: int = 20) -> list[bool]:
    """逐日跌破均线止损信号：收盘价从均线上方穿破到下方。"""
    closes = [b["close"] for b in bars]
    ma = moving_avg(closes, period)
    n = len(closes)
    out = [False] * n
    for i in range(1, n):
        if ma[i] is None or ma[i - 1] is None:
            continue
        if closes[i] < ma[i] and closes[i - 1] >= ma[i - 1]:
            out[i] = True
    return out


def daily_high_volume_drop_series(
    bars: list[dict], ma_period: int = 20, volume_lookback: int = 20, volume_mult: float = 1.5,
) -> list[bool]:
    """逐日高位放量阴线信号：收盘价在均线上方 + 当日阴线 + 当日量 > 近N日均量×倍数。"""
    closes = [b["close"] for b in bars]
    ma = moving_avg(closes, ma_period)
    n = len(bars)
    out = [False] * n
    for i in range(volume_lookback, n):
        if ma[i] is None:
            continue
        above_ma = bars[i]["close"] > ma[i]
        bearish = bars[i]["close"] < bars[i]["open"]
        avg_vol = sum(bars[j]["volume"] for j in range(i - volume_lookback, i)) / volume_lookback
        high_vol = avg_vol > 0 and bars[i]["volume"] >= avg_vol * volume_mult
        out[i] = bool(above_ma and bearish and high_vol)
    return out


def ma_death_cross_metrics(bars: list[dict], cross_days: int = 3) -> dict | None:
    """近 cross_days 日内 MA5 下穿 MA10（死叉）。"""
    if len(bars) < 11:
        return None
    closes = [b["close"] for b in bars]
    ma5 = moving_avg(closes, 5)
    ma10 = moving_avg(closes, 10)
    n = len(closes)
    death = any(
        ma5[n - 1 - k] is not None and ma10[n - 1 - k] is not None
        and ma5[n - 2 - k] is not None and ma10[n - 2 - k] is not None
        and ma5[n - 1 - k] < ma10[n - 1 - k] and ma5[n - 2 - k] >= ma10[n - 2 - k]
        for k in range(cross_days) if n - 2 - k >= 0
    )
    return {"death_cross": death}


def break_ma_metrics(bars: list[dict], ma_period: int = 20) -> dict | None:
    """最新K线收盘价从均线上方穿破均线下方。"""
    if len(bars) < ma_period + 1:
        return None
    closes = [b["close"] for b in bars]
    ma = moving_avg(closes, ma_period)
    if ma[-1] is None or ma[-2] is None:
        return None
    broke = closes[-1] < ma[-1] and closes[-2] >= ma[-2]
    return {"broke": broke}


def rsi_overbought_metrics(
    bars: list[dict], period: int = 14, threshold: float = 70.0, lookback_days: int = 2,
) -> dict | None:
    """近 lookback_days 日内 RSI 由>threshold 回落到 <=threshold。"""
    if len(bars) < period + lookback_days + 1:
        return None
    closes = [b["close"] for b in bars]
    rsi = compute_rsi(closes, period)
    n = len(closes)
    fell = any(
        rsi[n - 1 - k] is not None and rsi[n - 2 - k] is not None
        and rsi[n - 1 - k] <= threshold and rsi[n - 2 - k] > threshold
        for k in range(lookback_days) if n - 2 - k >= 0
    )
    return {"fell": fell}


def high_volume_drop_metrics(
    bars: list[dict], ma_period: int = 20, volume_lookback: int = 20, volume_mult: float = 1.5,
) -> dict | None:
    """最新K线：收盘在均线上方 + 阴线 + 成交量 > 近N日均量×倍数。"""
    if len(bars) < max(ma_period, volume_lookback) + 1:
        return None
    closes = [b["close"] for b in bars]
    ma = moving_avg(closes, ma_period)
    if ma[-1] is None:
        return None
    above_ma = bars[-1]["close"] > ma[-1]
    bearish = bars[-1]["close"] < bars[-1]["open"]
    avg_vol = sum(bars[i]["volume"] for i in range(-volume_lookback - 1, -1)) / volume_lookback
    high_vol = avg_vol > 0 and bars[-1]["volume"] >= avg_vol * volume_mult
    return {"above_ma": above_ma, "bearish": bearish, "high_vol": high_vol}
