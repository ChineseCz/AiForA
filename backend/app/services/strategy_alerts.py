"""Email alerts for saved strategy combinations."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.core.sync_db import sync_session
from app.repositories import sync_data as db
from app.services.notifications import _claim, _finish, _get_settings, _send_email
from app.services.strategy_review import BUY_STRATEGIES, SELL_STRATEGIES, _combine_series, _signal_series


def _today_signal(bars: list[dict], expression: dict, allowed: tuple[str, ...]) -> bool:
    if len(bars) < 23 or not isinstance(expression, dict):
        return False
    keys = expression.get("strategies")
    if not isinstance(keys, list) or not keys or any(not isinstance(key, str) or key not in allowed for key in keys):
        return False
    operator = expression.get("operator")
    if operator not in ("AND", "OR"):
        operator = "OR"
    series = [_signal_series(bars, key) for key in keys]
    combined = _combine_series(series, operator)
    return bool(combined and combined[-1])


def scan_strategy_email_alerts() -> int:
    """Send one daily email per enabled saved strategy when watchlist signals appear."""
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if now.weekday() >= 5 or (now.hour, now.minute) < (16, 20):
        return 0

    with sync_session() as session:
        latest_date = session.execute(text("SELECT MAX(trade_date) FROM stock_daily")).scalar()
        if not latest_date or str(latest_date) != now.date().isoformat():
            return 0
        rows = session.execute(text("""
            SELECT c.id AS strategy_id, c.user_id, c.name AS strategy_name,
                   c.buy_expression, c.sell_expression, m.code, m.name AS stock_name
            FROM saved_strategy_combinations c
            JOIN stock_groups g ON g.user_id=c.user_id AND g.is_paper=FALSE
            JOIN stock_group_members m ON m.group_id=g.id
            WHERE c.alerts_enabled=TRUE
            ORDER BY c.user_id, c.id, m.code
        """)).mappings().all()

    by_strategy: dict[tuple[str, int], dict] = {}
    for row in rows:
        key = (row["user_id"], row["strategy_id"])
        group = by_strategy.setdefault(key, {"row": row, "members": {}})
        group["members"].setdefault(row["code"], row["stock_name"])

    sent = 0
    history_cache: dict[str, list[dict]] = {}
    for (user_id, strategy_id), group in by_strategy.items():
        cfg = _get_settings(user_id)
        if not cfg.get("signal_enabled", False) or not cfg.get("email_enabled", False):
            continue
        signals: list[str] = []
        strategy = group["row"]
        for code, name in group["members"].items():
            if code not in history_cache:
                history_cache[code] = db.get_history_for_code(code)
            bars = history_cache[code]
            if not bars or str(bars[-1]["trade_date"]) != str(latest_date):
                continue
            buy = _today_signal(bars, strategy["buy_expression"], BUY_STRATEGIES)
            sell = _today_signal(bars, strategy["sell_expression"], SELL_STRATEGIES)
            if buy or sell:
                labels = "、".join(label for label, active in (("买入信号", buy), ("卖出信号", sell)) if active)
                signals.append(f"{name or code}（{code}）：{labels}")
        if not signals:
            continue

        event_key = f"strategy:{strategy_id}:{latest_date}"
        if not _claim(user_id, "email", event_key):
            continue
        content = "\n".join([
            f"策略：{strategy['strategy_name']}",
            f"交易日：{latest_date}",
            "",
            *signals,
            "",
            "以上为策略规则生成的信号提示，不构成投资建议。",
        ])
        with sync_session() as session:
            address = session.execute(text(
                "SELECT email FROM users WHERE email=:u OR phone=:u OR openid=:u"
            ), {"u": user_id}).scalar()
        ok = bool(address) and _send_email(address, f"【雪球看板】策略信号提醒：{strategy['strategy_name']}", content)
        _finish(user_id, "email", event_key, "sent" if ok else "error", "未绑定邮箱或邮件发送失败" if not ok else "")
        sent += int(ok)
    return sent
