"""
Integration tests for delta neutral backtest against real PostgreSQL data (#544).

Requires PostgreSQL on localhost:5432 with gex_options database.
Auto-skipped in CI via conftest.py hook.
"""

import numpy as np
import pytest

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.signals.delta_neutral_signal import DeltaNeutralSignal

pytestmark = pytest.mark.db


class TestVolDataAccess:
    """Verify delta neutral signal can load vol metrics from PostgreSQL."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000)
        yield
        self.bt.close()

    def test_spy_vol_data_available(self):
        """SPY IV-HV spread should be available for 2024."""
        signal = DeltaNeutralSignal(vol_spread_window=30)
        signal.load_vol_data(self.bt._get_connection(), "SPY", "2024-01-02", "2024-12-31")
        vol_data = signal.get_vol_data()
        assert len(vol_data) > 200, f"Expected 200+ rows, got {len(vol_data)}"
        assert "iv_hv_spread" in vol_data.columns

    def test_spread_stats_reasonable(self):
        """IV-RV spread stats should be in reasonable range."""
        signal = DeltaNeutralSignal(vol_spread_window=30)
        signal.load_vol_data(self.bt._get_connection(), "SPY", "2024-01-02", "2024-12-31")
        stats = signal.calculate_spread_stats()
        # IV-RV spread should be within reasonable bounds
        assert -0.5 < stats["mean"] < 0.5, f"Mean spread {stats['mean']} out of range"
        assert stats["std"] > 0, "Spread std should be positive"
        assert stats["n_obs"] > 200

    def test_vol_data_all_windows(self):
        """All three vol windows (10, 20, 30) should load."""
        for window in (10, 20, 30):
            signal = DeltaNeutralSignal(vol_spread_window=window)
            signal.load_vol_data(self.bt._get_connection(), "SPY", "2024-06-01", "2024-06-30")
            vol_data = signal.get_vol_data()
            assert len(vol_data) > 15, f"Window {window}: expected 15+ rows, got {len(vol_data)}"


class TestDeltaNeutralBacktest:
    """Test full delta neutral backtest."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)
        yield
        self.bt.close()

    def test_backtest_produces_valid_results(self):
        """Full delta neutral backtest should produce valid BacktestResults."""
        signal = DeltaNeutralSignal(
            vol_spread_window=30, entry_threshold=0.02, exit_threshold=0.005
        )
        signal.load_vol_data(self.bt._get_connection(), "SPY", "2024-01-02", "2024-12-31")

        prices = self.bt.get_close_prices(["SPY"], "2024-01-02", "2024-12-31")
        if len(prices) < 100:
            pytest.skip("Insufficient price data")

        results = self.bt.run_daily_signal_strategy(
            signal_fn=signal.generate_signal,
            prices=prices,
            symbol="SPY",
        )

        assert results.symbol == "SPY"
        assert np.isfinite(results.sharpe_ratio), "Sharpe must be finite"
        assert np.isfinite(results.total_return), "Return must be finite"
        assert results.final_value > 0, "Final value should be positive"

    def test_gex_overlay_regime_matches(self):
        """GEX overlay regime should match options_daily_summary regime."""
        overlay = self.bt.get_gex_overlay()
        signal = DeltaNeutralSignal(vol_spread_window=30)
        signal.load_vol_data(self.bt._get_connection(), "SPY", "2024-06-01", "2024-06-30")

        vol_data = signal.get_vol_data()
        if len(vol_data) == 0:
            pytest.skip("No vol data for period")

        # Check that overlay regime matches vol data regime for a sample date
        sample_date = vol_data.index[len(vol_data) // 2]
        overlay_regime = overlay.get_regime("SPY", sample_date)
        vol_regime = vol_data.loc[sample_date, "regime"] if sample_date in vol_data.index else None

        if vol_regime is not None and overlay_regime is not None:
            assert (
                overlay_regime == vol_regime
            ), f"Regime mismatch: overlay={overlay_regime}, vol_data={vol_regime}"

    def test_returns_series_finite(self):
        """All returns should be finite numbers."""
        signal = DeltaNeutralSignal(vol_spread_window=30, entry_threshold=0.02)
        signal.load_vol_data(self.bt._get_connection(), "SPY", "2024-01-02", "2024-06-30")

        prices = self.bt.get_close_prices(["SPY"], "2024-01-02", "2024-06-30")
        if len(prices) < 50:
            pytest.skip("Insufficient price data")

        results = self.bt.run_daily_signal_strategy(
            signal_fn=signal.generate_signal,
            prices=prices,
            symbol="SPY",
        )

        returns = results.returns_series.dropna()
        assert all(np.isfinite(returns)), "All returns must be finite"
