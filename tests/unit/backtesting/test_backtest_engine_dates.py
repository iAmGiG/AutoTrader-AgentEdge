"""BacktestEngine dates each daily return by the day it was earned."""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.backtesting.backtest_engine import BacktestEngine
from src.backtesting.portfolio import Portfolio


def _engine(data):
    engine = BacktestEngine.__new__(BacktestEngine)  # skip the market-data cache setup
    engine.initial_capital = 10_000.0
    engine.portfolio = Portfolio(10_000.0, 0.0)
    engine.cache = MagicMock(get=MagicMock(return_value=data))
    return engine


def _buy_on_first_day(symbol, history):
    return {"action": "BUY", "position_size": 1.0} if len(history) == 1 else {"action": "HOLD"}


def test_engine_returns_carry_the_day_they_were_earned():
    idx = pd.bdate_range("2024-01-01", periods=4)
    data = pd.DataFrame({"close": [100.0, 110.0, 121.0, 121.0]}, index=idx)

    res = _engine(data).run(_buy_on_first_day, "X", "2024-01-01", "2024-01-04")

    assert list(res.returns_series.index) == list(idx[1:])
    assert res.returns_series.loc[idx[1]] == pytest.approx(0.10)
    assert res.returns_series.loc[idx[3]] == pytest.approx(0.0)


def test_engine_dates_a_missing_price_day_too():
    idx = pd.bdate_range("2024-01-01", periods=4)
    data = pd.DataFrame({"close": [100.0, float("nan"), 110.0, 121.0]}, index=idx)

    res = _engine(data).run(_buy_on_first_day, "X", "2024-01-01", "2024-01-04")

    assert list(res.returns_series.index) == list(idx[1:])
    assert res.returns_series.loc[idx[1]] == 0
    assert res.returns_series.loc[idx[2]] == pytest.approx(0.10)
