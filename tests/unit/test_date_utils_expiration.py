"""Days to expiration on pandas 2 and 3 (pandas 3 gives strings the `str` dtype, not object)."""

from types import SimpleNamespace

import pandas as pd
import pytest

from src.backtesting.signals import pairs_trading_signal
from src.utils.date_utils import calculate_days_to_expiration

EXPIRIES = ["2026-11-20", "2026-12-18"]
TRADES = ["2026-10-20", "2026-10-20"]


@pytest.mark.parametrize("dtype", [None, object])  # the default string dtype, and object
def test_string_series_are_parsed(dtype):
    days = calculate_days_to_expiration(
        pd.Series(EXPIRIES, dtype=dtype), pd.Series(TRADES, dtype=dtype)
    )

    assert list(days) == [31, 59]


def test_datetime_series_are_used_as_they_are():
    days = calculate_days_to_expiration(
        pd.to_datetime(pd.Series(EXPIRIES)), pd.to_datetime(pd.Series(TRADES))
    )

    assert list(days) == [31, 59]


def test_single_dates_give_a_number_of_days():
    assert calculate_days_to_expiration("2026-11-20", "2026-10-20") == 31


@pytest.mark.parametrize(
    "result", [(-3.1, 0.03, 1, 99, {}, 0.0), SimpleNamespace(stat=-3.1, pvalue=0.03)]
)
def test_adf_pvalue_reads_a_tuple_or_a_result_object(monkeypatch, result):
    """statsmodels 0.15 still returns a tuple on request; later releases return an object."""
    monkeypatch.setattr(pairs_trading_signal, "adfuller", lambda *a, **k: result)

    assert pairs_trading_signal.adf_pvalue([1.0, 2.0, 3.0]) == 0.03
