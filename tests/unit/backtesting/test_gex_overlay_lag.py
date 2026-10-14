"""GEXOverlay regime lag (#576): same-day regime is look-ahead, so default lags by one."""

from unittest.mock import MagicMock

import pytest

from src.backtesting.gex_overlay import GEXOverlay

ROWS = [
    ("2024-01-02", "bullish_gamma", 1.0, 100.0),
    ("2024-01-03", "bearish_gamma", -2.0, 101.0),
    ("2024-01-04", "neutral", 0.5, 102.0),
]


def _overlay(**kwargs) -> GEXOverlay:
    import datetime as dt

    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = [
        (dt.date.fromisoformat(d), r, g, z) for d, r, g, z in ROWS
    ]
    return GEXOverlay(conn, **kwargs)


def test_default_lag_uses_prior_observation():
    ov = _overlay()
    assert ov.get_regime("SPY", "2024-01-03") == "bullish_gamma"
    assert ov.get_regime("SPY", "2024-01-04") == "bearish_gamma"


def test_default_lag_has_no_regime_on_first_day():
    assert _overlay().get_regime("SPY", "2024-01-02") is None


def test_lag_zero_is_same_day():
    ov = _overlay(lag_days=0)
    assert ov.get_regime("SPY", "2024-01-03") == "bearish_gamma"


def test_lag_two_goes_back_two_observations():
    ov = _overlay(lag_days=2)
    assert ov.get_regime("SPY", "2024-01-04") == "bullish_gamma"
    assert ov.get_regime("SPY", "2024-01-03") is None


def test_total_gex_is_lagged_too():
    assert _overlay().get_total_gex("SPY", "2024-01-04") == -2.0


def test_negative_lag_rejected():
    with pytest.raises(ValueError):
        _overlay(lag_days=-1)


def test_total_gex_missing_value_is_none():
    import datetime as dt

    conn = MagicMock()  # a row can have a regime but a NULL total_gex
    conn.cursor.return_value.fetchall.return_value = [
        (dt.date(2024, 1, 2), "bullish_gamma", None, 100.0)
    ]
    assert GEXOverlay(conn).get_total_gex("SPY", "2024-01-03") is None
