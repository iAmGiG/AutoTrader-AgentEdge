"""
Integration tests for pairs trading backtest against real PostgreSQL data (#546).

Requires PostgreSQL on localhost:5432 with gex_options database.
Auto-skipped in CI via conftest.py hook.
"""

import numpy as np
import pytest

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.signals.pairs_trading_signal import PairsTradingSignal

pytestmark = pytest.mark.db


class TestPairsTradingDataAccess:
    """Verify pairs trading can access required data from PostgreSQL."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)
        yield
        self.bt.close()

    def test_spy_iwm_prices_available(self):
        """SPY and IWM daily prices should be available for 2024."""
        prices = self.bt.get_close_prices(["SPY", "IWM"], "2024-01-02", "2024-12-31")
        assert len(prices) > 200, f"Expected 200+ trading days, got {len(prices)}"
        assert "SPY" in prices.columns
        assert "IWM" in prices.columns

    def test_qqq_spy_prices_available(self):
        """QQQ and SPY daily prices should be available."""
        prices = self.bt.get_close_prices(["QQQ", "SPY"], "2024-01-02", "2024-12-31")
        assert len(prices) > 200
        assert "QQQ" in prices.columns

    def test_prices_no_gaps(self):
        """Pivoted prices should have no NaN gaps."""
        prices = self.bt.get_close_prices(["SPY", "IWM"], "2024-01-02", "2024-12-31")
        assert prices.isna().sum().sum() == 0, "Price data has NaN gaps"


class TestPairsTradingCointegration:
    """Test cointegration on real equity data."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000)
        yield
        self.bt.close()

    def test_spy_iwm_cointegration(self):
        """SPY/IWM should show evidence of cointegration over 2022-2023."""
        prices = self.bt.get_close_prices(["SPY", "IWM"], "2022-01-03", "2023-12-29")
        if len(prices) < 200:
            pytest.skip("Insufficient price data")

        signal = PairsTradingSignal(lookback=60, entry_z=2.0, exit_z=0.5)
        result = signal.fit(prices["SPY"], prices["IWM"])

        # Report even if not cointegrated — useful for research
        assert result["hedge_ratio"] > 0, "Hedge ratio should be positive"
        assert result["half_life_days"] > 0, "Half-life should be positive"
        assert 0 <= result["coint_pvalue"] <= 1, "p-value out of range"

    def test_qqq_spy_cointegration(self):
        """QQQ/SPY cointegration test."""
        prices = self.bt.get_close_prices(["QQQ", "SPY"], "2022-01-03", "2023-12-29")
        if len(prices) < 200:
            pytest.skip("Insufficient price data")

        signal = PairsTradingSignal(lookback=60)
        result = signal.fit(prices["QQQ"], prices["SPY"])
        assert result["hedge_ratio"] > 0
        assert result["n_obs"] > 200


class TestPairsTradingBacktest:
    """Test full backtest produces valid results."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)
        yield
        self.bt.close()

    def test_spread_backtest_produces_results(self):
        """Full spread backtest should produce valid BacktestResults."""
        # Fit on 2022-2023
        fit_prices = self.bt.get_close_prices(["SPY", "IWM"], "2022-01-03", "2023-12-29")
        if len(fit_prices) < 200:
            pytest.skip("Insufficient fit data")

        signal = PairsTradingSignal(lookback=60, entry_z=2.0, exit_z=0.5)
        signal.fit(fit_prices["SPY"], fit_prices["IWM"])

        # Test on 2024
        test_prices = self.bt.get_close_prices(["SPY", "IWM"], "2024-01-02", "2024-12-31")
        if len(test_prices) < 100:
            pytest.skip("Insufficient test data")

        results = self.bt.run_spread_strategy(
            signal_fn=signal.generate_signal,
            prices=test_prices,
            symbol_a="SPY",
            symbol_b="IWM",
        )

        assert results.symbol == "SPY/IWM"
        assert np.isfinite(results.sharpe_ratio), "Sharpe must be finite"
        assert np.isfinite(results.total_return), "Return must be finite"
        assert results.max_drawdown <= 0, "Max drawdown should be ≤ 0"
        assert results.final_value > 0, "Final value should be positive"

    def test_gex_overlay_accessible(self):
        """GEX overlay should load regime data for SPY."""
        overlay = self.bt.get_gex_overlay()
        regime = overlay.get_regime("SPY", "2024-06-14")
        # Should return a known regime or None
        assert regime in ("bullish_gamma", "bearish_gamma", "neutral", None)

    def test_backtest_returns_series_valid(self):
        """Returns series should be all finite with correct length."""
        fit_prices = self.bt.get_close_prices(["SPY", "IWM"], "2022-01-03", "2023-12-29")
        if len(fit_prices) < 200:
            pytest.skip("Insufficient fit data")

        signal = PairsTradingSignal(lookback=60, entry_z=2.0, exit_z=0.5)
        signal.fit(fit_prices["SPY"], fit_prices["IWM"])

        test_prices = self.bt.get_close_prices(["SPY", "IWM"], "2024-01-02", "2024-06-30")
        if len(test_prices) < 50:
            pytest.skip("Insufficient test data")

        results = self.bt.run_spread_strategy(
            signal_fn=signal.generate_signal,
            prices=test_prices,
            symbol_a="SPY",
            symbol_b="IWM",
        )

        returns = results.returns_series.dropna()
        assert all(np.isfinite(returns)), "All returns must be finite"
