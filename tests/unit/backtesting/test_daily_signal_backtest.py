"""run_daily_signal_strategy applies direction and size and exits before booking (#576)."""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.research_backtester import ResearchBacktester


def _prices(n=5):
    idx = pd.bdate_range("2024-01-01", periods=n)
    return pd.DataFrame({"X": np.linspace(100, 104, n)}, index=idx)


def _run(script, commission_bps=0.0):
    """``script`` maps row index -> (action, position_size, daily_pnl_pct)."""
    bt = ResearchBacktester(initial_capital=100.0, commission_bps=commission_bps)

    def signal_fn(prices, i):
        action, size, pnl = script.get(i, ("HOLD", 0.0, 0.0))
        return {"action": action, "position_size": size, "daily_pnl_pct": pnl}

    return bt.run_daily_signal_strategy(signal_fn, _prices(), "X")


def test_sell_earns_negative_of_change():
    res = _run({1: ("SELL", 1.0, 0.0), 2: ("HOLD", 0.0, -0.10)})
    assert res.final_value == pytest.approx(110.0)


def test_buy_earns_change():
    res = _run({1: ("BUY", 1.0, 0.0), 2: ("HOLD", 0.0, 0.10)})
    assert res.final_value == pytest.approx(110.0)


def test_entry_size_scales_pnl():
    res = _run({1: ("BUY", 0.5, 0.0), 2: ("HOLD", 0.0, 0.10)})
    assert res.final_value == pytest.approx(105.0)


def test_exit_applies_before_booking_the_day():
    res = _run({1: ("BUY", 1.0, 0.0), 2: ("EXIT", 0.0, 0.50)})
    assert res.final_value == pytest.approx(100.0)


def test_entry_day_earns_that_day():
    # Signals use information through the prior day, so the entry day's change counts
    res = _run({1: ("BUY", 1.0, 0.10)})
    assert res.final_value == pytest.approx(110.0)


def test_size_fixed_at_entry():
    res = _run({1: ("BUY", 0.5, 0.0), 2: ("BUY", 1.5, 0.10)})
    assert res.final_value == pytest.approx(105.0)


def test_spread_strategy_marks_open_position_daily():
    idx = pd.bdate_range("2024-01-01", periods=4)
    # log spread a-b: 0, 0, 0.1, 0.2
    prices = pd.DataFrame({"A": np.exp([0.0, 0.0, 0.1, 0.2]), "B": [1.0, 1.0, 1.0, 1.0]}, index=idx)
    script = {1: "BUY", 3: "EXIT"}
    bt = ResearchBacktester(initial_capital=100.0, commission_bps=0.0)
    res = bt.run_spread_strategy(
        lambda p, i: {"action": script.get(i, "HOLD"), "position_size": 1.0}, prices, "A", "B"
    )
    assert res.final_value == pytest.approx(120.0)
    # day 2 is marked at +10% instead of being booked only at exit
    assert res.returns_series.iloc[1] == pytest.approx(0.10)
