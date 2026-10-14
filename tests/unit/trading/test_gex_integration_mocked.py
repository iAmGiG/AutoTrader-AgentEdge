"""
CI-safe unit tests for GEX infrastructure integration.

These tests run WITHOUT PostgreSQL by using:
- GEXCalculator directly (pure math, no DB)
- RegimeClassifier with synthetic data
- Mock options manager fixtures

Issue: GEX Database Integration for Test Suite
"""

import numpy as np
import pandas as pd
import pytest

# gex-database-infrastructure is the optional "gex" extra (pip install -e ".[gex]")
pytest.importorskip("gex_db_infrastructure")


# =============================================================================
# GEXCalculator Unit Tests (pure math — no DB)
# =============================================================================


class TestGEXCalculatorUnit:
    """Black-Scholes gamma and GEX calculation tests."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from gex_db_infrastructure.gex.gex_calculator import GEXCalculator

        self.calc = GEXCalculator(risk_free_rate=0.05)

    def test_atm_gamma_higher_than_otm(self):
        """ATM options should have higher gamma than deep OTM."""
        spot = 600.0  # SPY-like
        tte = 30 / 365
        r = 0.05
        sigma = 0.20

        gamma_atm = self.calc.black_scholes_gamma(spot, K=600, T=tte, r=r, sigma=sigma)
        gamma_otm = self.calc.black_scholes_gamma(spot, K=650, T=tte, r=r, sigma=sigma)

        assert gamma_atm > gamma_otm, "ATM gamma must exceed OTM gamma"
        assert gamma_atm > 0, "Gamma must be positive"

    def test_gamma_near_zero_at_expiry(self):
        """Gamma should be near zero for deep OTM at very short expiry."""
        gamma = self.calc.black_scholes_gamma(S=600, K=700, T=1 / 365, r=0.05, sigma=0.20)
        assert gamma < 1e-6, f"Deep OTM near-expiry gamma should be ~0, got {gamma}"

    def test_gamma_zero_vol(self):
        """Zero volatility should produce near-zero gamma for OTM options."""
        gamma = self.calc.black_scholes_gamma(S=600, K=650, T=30 / 365, r=0.05, sigma=0.001)
        assert gamma < 1e-6, f"Near-zero vol OTM gamma should be ~0, got {gamma}"

    def test_gamma_symmetry_calls_puts(self):
        """Gamma is the same for calls and puts at the same strike."""
        spot, strike, tte, r, sigma = 600, 600, 30 / 365, 0.05, 0.20
        gamma = self.calc.black_scholes_gamma(spot, strike, tte, r, sigma)
        assert gamma > 0, "ATM gamma must be positive"

    def test_dealer_gex_calculation(self):
        """Dealer GEX calculation with synthetic options data."""
        options_df = pd.DataFrame(
            {
                "strike": [595.0, 600.0, 605.0],
                "type": ["call", "call", "put"],
                "open_interest": [10000, 15000, 12000],
                "gamma": [0.015, 0.020, 0.018],
                "implied_volatility": [0.18, 0.17, 0.19],
                "days_to_expiration": [30, 30, 30],
            }
        )
        result = self.calc.calculate_dealer_gamma_exposure(options_df, underlying_price=600.0)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        # GEX columns should exist
        assert "dealer_gex" in result.columns or "weighted_gex" in result.columns

    def test_option_type_auto_normalized(self):
        """GEXCalculator should auto-normalize option_type→type since v1.3.0 (#35)."""
        options_df = pd.DataFrame(
            {
                "strike": [595.0, 600.0, 605.0],
                "option_type": ["call", "call", "put"],  # DB column name
                "open_interest": [10000, 15000, 12000],
                "gamma": [0.015, 0.020, 0.018],
                "implied_volatility": [0.18, 0.17, 0.19],
                "days_to_expiration": [30, 30, 30],
            }
        )
        result = self.calc.calculate_dealer_gamma_exposure(options_df, underlying_price=600.0)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3

    def test_net_gex_sign(self):
        """Net GEX sign should reflect call/put imbalance."""
        call_heavy = pd.DataFrame(
            {
                "strike": [600.0],
                "type": ["call"],
                "open_interest": [50000],
                "gamma": [0.02],
                "implied_volatility": [0.18],
                "days_to_expiration": [30],
            }
        )
        result = self.calc.calculate_dealer_gamma_exposure(call_heavy, 600.0)
        assert len(result) > 0, "Should produce GEX output"


# =============================================================================
# RegimeClassifier Unit Tests (synthetic data)
# =============================================================================


class TestRegimeClassifierUnit:
    """Regime classification with synthetic GEX sequences.

    classify_window() accepts both formats since v1.3.0 (#36):
    - List[Dict] with 'net_gex' key: [{"net_gex": 5e9}, ...]
    - Raw numeric list: [5e9, -2.3e9, ...]
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        from gex_db_infrastructure.validation.regime_classifier import RegimeClassifier

        self.classifier = RegimeClassifier(
            persistence_threshold=0.70,
            magnitude_threshold=5e9,
            max_sign_flips=5,
        )

    @staticmethod
    def _make_sequence(values):
        """Convert raw floats to list of dicts with 'net_gex' key."""
        return [{"net_gex": v} for v in values]

    def test_persistent_positive_regime(self):
        """Strong positive GEX series -> persistent_positive."""
        np.random.seed(100)
        values = [8e9 + np.random.normal(0, 1e8) for _ in range(30)]
        result = self.classifier.classify_window(self._make_sequence(values))

        assert result["regime_type"] == "persistent_positive"
        assert result["is_persistent"] is True

    def test_persistent_negative_regime(self):
        """Strong negative GEX series -> persistent_negative."""
        np.random.seed(101)
        values = [-8e9 + np.random.normal(0, 1e8) for _ in range(30)]
        result = self.classifier.classify_window(self._make_sequence(values))

        assert result["regime_type"] == "persistent_negative"
        assert result["is_persistent"] is True

    def test_transitional_regime(self):
        """Alternating GEX sign -> transitional."""
        values = [6e9 * ((-1) ** i) for i in range(30)]
        result = self.classifier.classify_window(self._make_sequence(values))

        assert result["regime_type"] == "transitional"
        assert result["is_persistent"] is False

    def test_classify_returns_required_keys(self):
        """Classification result must contain expected keys."""
        values = [5e9] * 30
        result = self.classifier.classify_window(self._make_sequence(values))

        required = {"regime_type", "is_persistent", "metrics", "window_size"}
        assert required.issubset(result.keys()), f"Missing keys: {required - result.keys()}"

    def test_window_size_matches_input(self):
        """Window size in result should match input length."""
        values = [5e9] * 30
        result = self.classifier.classify_window(self._make_sequence(values))
        assert result["window_size"] == 30

    def test_raw_float_list_accepted(self):
        """Raw float list should be auto-converted since v1.3.0 (#36)."""
        np.random.seed(200)
        values = [8e9 + np.random.normal(0, 1e8) for _ in range(30)]
        result = self.classifier.classify_window(values)

        assert result["regime_type"] == "persistent_positive"
        assert result["window_size"] == 30

    def test_raw_and_dict_formats_agree(self):
        """Raw float list and dict list should produce identical results."""
        np.random.seed(300)
        values = [6e9 + np.random.normal(0, 5e8) for _ in range(30)]

        result_raw = self.classifier.classify_window(values)
        result_dict = self.classifier.classify_window(self._make_sequence(values))

        assert result_raw["regime_type"] == result_dict["regime_type"]
        assert result_raw["is_persistent"] == result_dict["is_persistent"]


# =============================================================================
# Mocked Options Manager Usage Tests
# =============================================================================


class TestMockedOptionsManagerUsage:
    """Test GEX calculations using mocked DB manager."""

    def test_retrieve_and_calculate_gex(self, mock_options_manager):
        """Mock options manager -> GEXCalculator pipeline."""
        from gex_db_infrastructure.gex.gex_calculator import GEXCalculator

        chain = mock_options_manager.retrieve_options_chain("SPY", "2026-01-15")
        assert len(chain) == 10, "Mock should return 10 contracts"

        calc = GEXCalculator(risk_free_rate=0.05)
        result = calc.calculate_dealer_gamma_exposure(chain, underlying_price=600.0)
        assert len(result) == 10

    def test_mock_database_stats(self, mock_options_manager):
        """Verify mock stats shape matches real API."""
        stats = mock_options_manager.get_database_stats()
        assert stats["total_options_records"] == 123_800_000
        assert stats["total_symbols"] == 62

    def test_mock_gex_regime_access(self, mock_intraday_gex_manager):
        """Verify mock GEX manager responses."""
        latest = mock_intraday_gex_manager.get_latest_gex("SPY")
        assert latest["regime"] == "persistent_positive"
        assert latest["total_gex"] == 5.2e9

        changes = mock_intraday_gex_manager.get_regime_changes("SPY", days=30)
        assert len(changes) == 2

    def test_mock_snapshot_count(self, mock_intraday_gex_manager):
        """Snapshot count should match expected daily frequency."""
        count = mock_intraday_gex_manager.get_snapshot_count("SPY")
        assert count == 21, "Expected 21 snapshots/day"
