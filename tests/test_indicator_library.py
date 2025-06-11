import unittest
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.processors.indicator_library import ema, sma, rsi, atr, supertrend, avwap


class TestIndicatorLibrary(unittest.TestCase):
    def test_ema(self):
        series = pd.Series([1, 2, 3, 4, 5])
        result = ema(series, span=2)
        expected = series.ewm(span=2, adjust=False).mean()
        pd.testing.assert_series_equal(result, expected)

    def test_sma(self):
        series = pd.Series([1, 2, 3, 4])
        result = sma(series, window=2)
        expected = series.rolling(window=2).mean()
        pd.testing.assert_series_equal(result, expected)

    def test_rsi_increasing(self):
        series = pd.Series([1, 2, 3, 4, 5, 6])
        result = rsi(series, period=2)
        # Last value should be 100 for strictly increasing series
        self.assertAlmostEqual(result.iloc[-1], 100.0)

    def test_avwap(self):
        close = pd.Series([1, 2, 3])
        volume = pd.Series([1, 1, 1])
        result = avwap(close, volume, anchor_idx=0)
        expected = pd.Series([1.0, 1.5, 2.0])
        pd.testing.assert_series_equal(result, expected)

    def test_atr(self):
        high = pd.Series([2, 3, 4])
        low = pd.Series([1, 1, 2])
        close = pd.Series([1.5, 2.5, 3.5])
        result = atr(high, low, close, period=2)
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ], axis=1).max(axis=1)
        expected = tr.rolling(2).mean()
        pd.testing.assert_series_equal(result, expected)

    def test_supertrend_output_length(self):
        high = pd.Series([2, 3, 4, 5])
        low = pd.Series([1, 1, 2, 3])
        close = pd.Series([1.5, 2.5, 3.5, 4.5])
        result = supertrend(high, low, close, period=2, mult=1.0)
        self.assertEqual(len(result), len(close))
        # supertrend may start with NaN due to ATR warm-up
        self.assertLessEqual(result.isna().sum(), 1)


if __name__ == "__main__":
    unittest.main()
