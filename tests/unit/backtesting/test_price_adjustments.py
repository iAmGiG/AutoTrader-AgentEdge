"""Split adjustment of raw equity_prices_daily rows (the table does not adjust)."""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.price_adjustments import split_adjust


def _prices(symbol, closes, start="2020-08-26", volume=1000.0):
    dates = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame(
        {
            "trading_date": dates,
            "symbol": symbol,
            "open": closes,
            "high": [c * 1.01 for c in closes],
            "low": [c * 0.99 for c in closes],
            "close": closes,
            "volume": volume,
        }
    )


def _splits(*rows):
    return pd.DataFrame(rows, columns=["symbol", "event_date", "split_factor"]).assign(
        event_date=lambda d: pd.to_datetime(d["event_date"])
    )


def test_forward_split_removes_the_fake_drop():
    # AAPL 4-for-1 on 2020-08-31: raw closes 500, 499 then 129, 134
    raw = _prices("AAPL", [500.0, 499.0, 129.0, 134.0], start="2020-08-27")

    adjusted = split_adjust(raw, _splits(("AAPL", "2020-08-31", 4.0)))

    assert list(adjusted["close"]) == pytest.approx([125.0, 124.75, 129.0, 134.0])
    assert adjusted["close"].pct_change().abs().max() < 0.05
    assert list(adjusted["volume"]) == pytest.approx([4000.0, 4000.0, 1000.0, 1000.0])
    assert list(adjusted["high"])[0] == pytest.approx(505.0 / 4)


def test_reverse_split_and_other_symbols_untouched():
    # TZA 1-for-10 on 2026-07-15: price jumps 10x
    tza = _prices("TZA", [5.0, 5.1, 51.5, 52.0], start="2026-07-13")
    spy = _prices("SPY", [600.0, 601.0, 602.0, 603.0], start="2026-07-13")

    adjusted = split_adjust(pd.concat([tza, spy]), _splits(("TZA", "2026-07-15", 0.1)))

    tza_adj = adjusted[adjusted["symbol"] == "TZA"]["close"]
    assert list(tza_adj) == pytest.approx([50.0, 51.0, 51.5, 52.0])
    assert list(adjusted[adjusted["symbol"] == "SPY"]["close"]) == [600.0, 601.0, 602.0, 603.0]


def test_multiple_splits_compound():
    raw = _prices("NVDA", [400.0, 100.0, 1000.0 / 4 / 10 * 4, 10.0], start="2024-06-05")
    splits = _splits(("NVDA", "2024-06-06", 4.0), ("NVDA", "2024-06-10", 10.0))

    adjusted = split_adjust(raw, splits)

    assert adjusted["close"].iloc[0] == pytest.approx(400.0 / 40)
    assert adjusted["close"].iloc[1] == pytest.approx(100.0 / 10)


def test_no_splits_returns_an_equal_copy():
    raw = _prices("SPY", [1.0, 2.0, 3.0])

    adjusted = split_adjust(raw, _splits())

    assert adjusted is not raw
    pd.testing.assert_frame_equal(adjusted, raw)
    assert np.isfinite(adjusted["close"]).all()
