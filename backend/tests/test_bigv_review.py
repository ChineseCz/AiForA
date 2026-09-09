from datetime import datetime

from app.api.routers.public.stocks import _before_realtime_start
from app.services.bigv_review import _claims_signature, _direction, _pct, _summary
from app.services.external.sina import is_realtime_session_started
from app.services.matching import fuzzy_match_instruments
from app.services.national_team import infer_exit_rows


def test_realtime_quote_gate_starts_at_0915_on_weekdays():
    assert _before_realtime_start(datetime(2026, 9, 9, 9, 14, 59)) is True
    assert _before_realtime_start(datetime(2026, 9, 9, 9, 15, 0)) is False
    assert _before_realtime_start(datetime(2026, 9, 12, 10, 0, 0)) is True
    assert is_realtime_session_started(datetime(2026, 9, 9, 9, 15, 0)) is True


def test_direction_uses_more_specific_signal_count():
    assert _direction("突破机会，继续看多") == "看多"
    assert _direction("风险回落，建议减仓") == "看空"
    assert _direction("市场观察") == "未定向"
    assert _direction("看多突破。风险提示：股市有风险，建议谨慎") == "看多"


def test_pct_handles_normal_and_invalid_values():
    assert _pct(100, 108) == 8.0
    assert _pct(100, 95) == -5.0
    assert _pct(0, 100) is None
    assert _pct(100, 0) is None
    assert _pct(100, -1) is None
    assert _pct(None, 100) is None


def test_claims_signature_is_stable_and_changes_with_mapping():
    claim = {"id": 1, "code": "600000", "name": "浦发银行", "direction": "看多", "status": "ready", "ignored": False}
    assert _claims_signature([claim]) == _claims_signature([dict(claim)])
    assert _claims_signature([claim]) != _claims_signature([{**claim, "code": "000001"}])


def test_summary_ignores_missing_windows_and_aggregates_excess():
    summary = _summary([
        {"user_id": "u1", "user_name": "大V", "direction": "看多",
         "claims": [{"status": "ready", "ignored": False}, {"status": "ready", "ignored": True}],
         "targets": [{"quote_count": 2, "performance": {"1": 2.0, "5": 10.0}, "excess": {"1": 1.0, "5": 7.0}}]},
        {"user_id": "u1", "user_name": "大V", "direction": "看空", "claims": [], "targets": []},
    ])
    assert summary["posts"] == 2
    assert summary["verified_posts"] == 1
    assert summary["claims"] == 1
    assert summary["windows"]["5"]["average_return"] == 10.0
    assert summary["windows"]["5"]["average_excess"] == 7.0
    assert summary["windows"]["5"]["positive_rate"] == 100.0


def test_summary_calculates_direction_accuracy_per_window():
    summary = _summary([{"user_id": "u1", "direction": "看多", "claims": [], "targets": [
        {"direction": "看多", "quote_count": 2, "performance": {"1": 2.0}, "excess": {"1": 1.0}},
        {"direction": "看空", "quote_count": 2, "performance": {"1": 3.0}, "excess": {"1": 2.0}},
    ]}])
    assert summary["windows"]["1"]["samples"] == 1
    assert summary["windows"]["1"]["average_return"] == 2.0
    assert summary["accuracy"]["1"]["samples"] == 1
    assert summary["accuracy"]["1"]["correct_rate"] == 100.0
    assert summary["accuracy"]["1"]["benchmark_win_rate"] == 100.0
    assert summary["accuracy"]["1"]["target_hit_rate"] == 0.0


def test_national_team_exit_is_inferred_only_for_next_report_period():
    rows = [
        {"report_date": "2024-06-30", "institution": "中央汇金", "code": "600000", "name": "浦发银行", "shares": 1000},
        {"report_date": "2024-06-30", "institution": "中央汇金", "code": "000001", "name": "平安银行", "shares": 500},
        {"report_date": "2024-09-30", "institution": "中央汇金", "code": "600000", "name": "浦发银行", "shares": 1200},
    ]
    exits = [row for row in infer_exit_rows(rows) if row.get("change_type") == "退出披露范围"]
    assert len(exits) == 1
    assert exits[0]["code"] == "000001"
    assert exits[0]["report_date"] == "2024-09-30"
    assert exits[0]["change_shares"] == -500


def test_fuzzy_stock_aliases_support_mixed_pinyin_and_small_typo():
    candidates = [
        {"code": "600692", "name": "亚信科技"},
        {"code": "002761", "name": "浙江建投"},
        {"code": "600127", "name": "金健米业"},
    ]
    assert fuzzy_match_instruments(candidates, "亚信KJ")[0]["name"] == "亚信科技"
    assert fuzzy_match_instruments(candidates, "浙江JT")[0]["name"] == "浙江建投"
    assert fuzzy_match_instruments(candidates, "金键MY")[0]["name"] == "金健米业"
