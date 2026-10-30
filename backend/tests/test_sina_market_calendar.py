from datetime import datetime

from app.services.external import sina


def test_current_market_trade_date_rejects_holiday_when_index_quote_is_stale(monkeypatch):
    monkeypatch.setattr(sina, "fetch_realtime_quote", lambda _code: {"trade_date": "2026-09-24"})

    assert sina.current_market_trade_date(datetime(2026, 9, 25, 10, 0)) is None


def test_current_market_trade_date_accepts_matching_live_index_quote(monkeypatch):
    monkeypatch.setattr(sina, "fetch_realtime_quote", lambda _code: {"trade_date": "2026-10-29"})

    assert sina.current_market_trade_date(datetime(2026, 10, 29, 10, 0)) == "2026-10-29"


def test_current_market_trade_date_does_not_request_quote_on_weekend(monkeypatch):
    monkeypatch.setattr(
        sina,
        "fetch_realtime_quote",
        lambda _code: (_ for _ in ()).throw(AssertionError("no quote expected")),
    )

    assert sina.current_market_trade_date(datetime(2026, 9, 26, 10, 0)) is None
