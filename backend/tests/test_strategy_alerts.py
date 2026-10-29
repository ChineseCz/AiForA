from app.services import strategy_alerts


def test_today_signal_combines_selected_rules_for_latest_bar(monkeypatch):
    bars = [{"close": 1}] * 23

    def signals(_bars, key):
        return [False] * 22 + [key == "buy_a"]

    monkeypatch.setattr(strategy_alerts, "_signal_series", signals)
    allowed = ("buy_a", "buy_b")

    assert strategy_alerts._today_signal(bars, {"operator": "OR", "strategies": ["buy_a", "buy_b"]}, allowed)
    assert not strategy_alerts._today_signal(bars, {"operator": "AND", "strategies": ["buy_a", "buy_b"]}, allowed)


def test_today_signal_rejects_empty_or_unknown_rules(monkeypatch):
    monkeypatch.setattr(strategy_alerts, "_signal_series", lambda *_: [True] * 23)
    bars = [{"close": 1}] * 23

    assert not strategy_alerts._today_signal(bars, {"operator": "OR", "strategies": []}, ("buy_a",))
    assert not strategy_alerts._today_signal(bars, {"operator": "OR", "strategies": ["unknown"]}, ("buy_a",))
    assert not strategy_alerts._today_signal(bars[:22], {"operator": "OR", "strategies": ["buy_a"]}, ("buy_a",))
