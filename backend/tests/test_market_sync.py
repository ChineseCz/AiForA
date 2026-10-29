from datetime import datetime as real_datetime

from app.core.config import settings
from app.repositories import jobs, sync_data
from app.services import ingest
from app.services.external import sina
from app.workers.tasks import stock


class FixedDateTime(real_datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 29, 10, 0, 21, tzinfo=tz)


def test_auto_sync_dispatches_during_session_without_same_day_index_bar(monkeypatch):
    import datetime
    import redis

    class FakeRedis:
        def set(self, *args, **kwargs):
            return True

        def close(self):
            pass

    monkeypatch.setattr(datetime, "datetime", FixedDateTime)
    monkeypatch.setattr(sync_data, "get_schedule", lambda: {
        "stock_auto_sync_enabled": True,
        "stock_sync_interval": 15,
    })
    monkeypatch.setattr(jobs, "is_running", lambda _kind: False)
    monkeypatch.setattr(redis, "from_url", lambda *_args, **_kwargs: FakeRedis())
    monkeypatch.setattr(settings, "redis_url", "redis://test/0")
    dispatched = []
    monkeypatch.setattr(stock.task_stock_sync, "delay", lambda **kwargs: dispatched.append(kwargs))

    stock.task_auto_sync_tick.run()

    assert dispatched == [{"source": "定时(15分钟)"}]


def test_daily_snapshot_does_not_require_same_day_index_bar(monkeypatch):
    monkeypatch.setattr(sina, "is_realtime_session_started", lambda: True)
    monkeypatch.setattr(sina, "fetch_spot_snapshot", lambda: [])
    monkeypatch.setattr(sina, "fetch_etf_snapshot", lambda: [])
    monkeypatch.setattr(sina, "fetch_bond_snapshot", lambda: [])
    monkeypatch.setattr(ingest.db, "save_snapshot", lambda *_args: 1)
    monkeypatch.setattr(ingest.db, "save_bond_snapshot", lambda *_args: 2)

    assert ingest.sync_daily_snapshot() == 4
