"""
Integration tests for dispersion trading backtest against real PostgreSQL data (#545).

Requires PostgreSQL on localhost:5432 with gex_options database.
Auto-skipped in CI via conftest.py hook.
"""

import numpy as np
import pytest

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.signals.dispersion_signal import DispersionSignal

pytestmark = pytest.mark.db

INDEX = "SPY"
COMPONENTS = ["XLF", "XLE", "XLK", "XLV"]


class TestDispersionDataAccess:
    """Verify dispersion strategy can access required multi-symbol data."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000)
        yield
        self.bt.close()

    def test_multi_symbol_prices_available(self):
        """All required symbols should have price data for 2024."""
        all_symbols = [INDEX] + COMPONENTS
        prices = self.bt.get_close_prices(all_symbols, "2024-01-02", "2024-12-31")
        assert len(prices) > 200, f"Expected 200+ trading days, got {len(prices)}"
        for sym in all_symbols:
            assert sym in prices.columns, f"Missing symbol: {sym}"

    def test_returns_calculable(self):
        """Daily returns should be computable without NaN issues."""
        prices = self.bt.get_close_prices([INDEX] + COMPONENTS, "2024-01-02", "2024-12-31")
        returns = prices.pct_change().dropna()
        assert len(returns) > 200
        assert returns.isna().sum().sum() == 0


class TestDispersionCorrelation:
    """Test realized correlation on real data."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000)
        yield
        self.bt.close()

    def test_realized_correlation_reasonable(self):
        """Realized correlation should be in reasonable range for equity ETFs."""
        prices = self.bt.get_close_prices([INDEX] + COMPONENTS, "2022-01-03", "2024-12-31")
        returns = prices.pct_change().dropna()

        signal = DispersionSignal(correlation_lookback=60, zscore_lookback=120)
        stats = signal.fit(returns, INDEX, COMPONENTS)

        # Equity ETFs should show moderate-to-high correlation
        assert (
            stats["mean_correlation"] > 0.2
        ), f"Expected positive mean correlation, got {stats['mean_correlation']:.3f}"
        assert stats["n_obs"] > 400, f"Expected 400+ observations, got {stats['n_obs']}"


class TestDispersionBacktest:
    """Test full dispersion backtest."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)
        yield
        self.bt.close()

    def test_backtest_produces_valid_results(self):
        """Full dispersion backtest should produce valid BacktestResults."""
        # Fit on 2022-2023
        all_symbols = [INDEX] + COMPONENTS
        full_prices = self.bt.get_close_prices(all_symbols, "2022-01-03", "2024-12-31")
        full_returns = full_prices.pct_change().dropna()

        signal = DispersionSignal(
            correlation_lookback=60, zscore_lookback=120, entry_z=1.5, exit_z=0.5
        )
        signal.fit(full_returns, INDEX, COMPONENTS)

        # Test on 2024
        test_prices = self.bt.get_close_prices(all_symbols, "2024-01-02", "2024-12-31")
        if len(test_prices) < 100:
            pytest.skip("Insufficient test data")

        results = self.bt.run_daily_signal_strategy(
            signal_fn=signal.generate_signal,
            prices=test_prices,
            symbol=INDEX,
        )

        assert results.symbol == INDEX
        assert np.isfinite(results.sharpe_ratio), "Sharpe must be finite"
        assert np.isfinite(results.total_return), "Return must be finite"
        assert results.final_value > 0, "Final value should be positive"

    def test_gex_overlay_accessible(self):
        """GEX overlay should be accessible for the dispersion strategy."""
        overlay = self.bt.get_gex_overlay()
        regime = overlay.get_regime(INDEX, "2024-06-14")
        assert regime in ("bullish_gamma", "bearish_gamma", "neutral", None)

    def test_returns_series_finite(self):
        """All returns should be finite numbers."""
        all_symbols = [INDEX] + COMPONENTS
        full_prices = self.bt.get_close_prices(all_symbols, "2022-01-03", "2024-06-30")
        full_returns = full_prices.pct_change().dropna()

        signal = DispersionSignal(correlation_lookback=60, zscore_lookback=120)
        signal.fit(full_returns, INDEX, COMPONENTS)

        test_prices = self.bt.get_close_prices(all_symbols, "2024-01-02", "2024-06-30")
        if len(test_prices) < 50:
            pytest.skip("Insufficient test data")

        results = self.bt.run_daily_signal_strategy(
            signal_fn=signal.generate_signal,
            prices=test_prices,
            symbol=INDEX,
        )

        returns = results.returns_series.dropna()
        assert all(np.isfinite(returns)), "All returns must be finite"
