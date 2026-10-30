from app.services.strategy_review import _annualized_return, _is_locked_limit_up, _is_st_name, _max_drawdown, _select_entry_candidates, _signal_series


def _candidate(code: str, name: str, change: float):
    return {"code": code, "bar": {"name": name, "change_pct": change}}


def test_st_filter_matches_st_and_star_st_names_with_spaces():
    assert _is_st_name("*ST 示例") is True
    assert _is_st_name(" ST示例 ") is True
    assert _is_st_name("示例科技") is False


def test_st_filter_removes_only_new_entry_candidates():
    candidates = [_candidate("600001", "*ST甲", 1.0), _candidate("600002", "乙", 2.0)]
    assert [x["code"] for x in _select_entry_candidates(candidates, exclude_st=True)] == ["600002"]


def test_locked_limit_up_is_not_executable():
    bar = {"open": 27.69, "high": 27.69, "low": 27.69, "close": 27.69, "change_pct": 10.0}
    assert _is_locked_limit_up("603221", bar) is True


def test_limit_up_with_intraday_range_is_not_marked_locked():
    bar = {"open": 25.90, "high": 27.69, "low": 25.90, "close": 27.69, "change_pct": 10.0}
    assert _is_locked_limit_up("603221", bar) is False


def test_performance_helpers_report_drawdown_and_annualized_return():
    assert _max_drawdown([100, 110, 99, 120]) == -10.0
    assert _annualized_return(100, 110, 365) == 10.0


def test_extended_buy_and_stop_loss_series_are_available():
    bars = [{"open": 10, "close": 10 + i * 0.1, "high": 10 + i * 0.1, "low": 10, "volume": 100 + i} for i in range(40)]
    assert len(_signal_series(bars, "pullback_low_volume")) == len(bars)
    assert len(_signal_series(bars, "volume_price_up")) == len(bars)
    assert len(_signal_series(bars, "sell_stop_loss")) == len(bars)
