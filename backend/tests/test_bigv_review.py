from app.services.bigv_review import _direction, _pct, _summary


def test_direction_uses_more_specific_signal_count():
    assert _direction("突破机会，继续看多") == "看多"
    assert _direction("风险回落，建议减仓") == "看空"
    assert _direction("市场观察") == "未定向"
    assert _direction("看多突破。风险提示：股市有风险，建议谨慎") == "看多"


def test_pct_handles_normal_and_invalid_values():
    assert _pct(100, 108) == 8.0
    assert _pct(100, 95) == -5.0
    assert _pct(0, 100) is None
    assert _pct(None, 100) is None


def test_summary_ignores_missing_windows_and_aggregates_excess():
    summary = _summary([
        {
            "user_id": "u1", "user_name": "大V", "direction": "看多",
            "claims": [{"status": "ready", "ignored": False}, {"status": "ready", "ignored": True}],
            "targets": [{
                "performance": {"1": 2.0, "5": 10.0},
                "excess": {"1": 1.0, "5": 7.0},
            }],
        },
        {
            "user_id": "u1", "user_name": "大V", "direction": "看空",
            "claims": [], "targets": [],
        },
    ])
    assert summary["posts"] == 2
    assert summary["verified_posts"] == 1
    assert summary["claims"] == 1
    assert summary["windows"]["5"]["average_return"] == 10.0
    assert summary["windows"]["5"]["average_excess"] == 7.0
    assert summary["windows"]["5"]["positive_rate"] == 100.0
