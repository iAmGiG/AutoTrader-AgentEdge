"""
Integration tests for MACD+RSI regime analysis against real PostgreSQL data (#531).

Requires PostgreSQL on localhost:5432 with gex_options database.
Auto-skipped in CI via conftest.py hook.
"""

import numpy as np
import pytest

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.signals.macd_rsi_signal import MACDRSISignal

pytestmark = pytest.mark.db


class TestMACDRSIDataAccess:
    """Verify MACD+RSI signal can access required data."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000)
        yield
        self.bt.close()

    def test_spy_prices_available(self):
        """SPY should have price data for 2020-2023."""
        prices = self.bt.get_close_prices(["SPY"], "2020-01-02", "2023-12-29")
        assert len(prices) > 900, f"Expected 900+ days, got {len(prices)}"

    def test_regime_data_available(self):
        """GEX regime should be available for SPY."""
        overlay = self.bt.get_gex_overlay()
        regime = overlay.get_regime("SPY", "2022-06-15")
        assert regime in ("bullish_gamma", "bearish_gamma", "neutral", None)


class TestMACDRSIBacktest:
    """Test full MACD+RSI backtest with regime stratification."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)
        yield
        self.bt.close()

    def test_backtest_produces_valid_results(self):
        """Full MACD+RSI backtest should produce valid results."""
        prices = self.bt.get_close_prices(["SPY"], "2020-01-02", "2023-12-29")
        signal = MACDRSISignal()
        results = self.bt.run_daily_signal_strategy(
            signal_fn=signal.generate_signal, prices=prices, symbol="SPY"
        )
        assert np.isfinite(results.sharpe_ratio)
        assert np.isfinite(results.total_return)
        assert results.final_value > 0

    def test_regime_split_has_enough_days(self):
        """Each regime bucket should have enough days for statistical analysis."""
        prices = self.bt.get_close_prices(["SPY"], "2021-01-04", "2023-12-29")
        overlay = self.bt.get_gex_overlay()
        regime_counts = {"bullish_gamma": 0, "bearish_gamma": 0, "neutral": 0}
        for date in prices.index:
            regime = overlay.get_regime("SPY", date)
            if regime in regime_counts:
                regime_counts[regime] += 1

        # Each regime should have at least 50 days
        for regime, count in regime_counts.items():
            assert count > 50, f"{regime} has only {count} days"

    def test_multiple_symbols(self):
        """Should work for QQQ and IWM too."""
        for sym in ["QQQ", "IWM"]:
            prices = self.bt.get_close_prices([sym], "2021-01-04", "2023-12-29")
            if len(prices) < 100:
                pytest.skip(f"Insufficient data for {sym}")
            signal = MACDRSISignal()
            results = self.bt.run_daily_signal_strategy(
                signal_fn=signal.generate_signal, prices=prices, symbol=sym
            )
            assert np.isfinite(results.sharpe_ratio)
