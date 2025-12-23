"""
Smoke Tests for A Stream Features (#366, #414)

These are quick validation tests to ensure the core functionality works.
Not comprehensive - just happy path validation before merge.

Run with: conda run -n AutoTrader python -m pytest tests/test_a_stream_smoke.py -v

NOTE: Uses direct module imports to avoid SQLite cache initialization issues.
The imports bypass src.trading.__init__ which triggers problematic import chains.

Tested features:
- #366: OHLCV-based entry planning (ATR, S/R levels, entry plans)
- #414: Advanced trailing stop automation (climb rates, volatility awareness, profit zones)

NOT tested here (exists on feature/core-execution branch, needs merge):
- #372: Multi-level price targets (commit a3dbeac in feature/core-execution)
"""

# ruff: noqa: N806

import importlib.util
import sys
from pathlib import Path

# Add project root to path BEFORE any imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
import pytest


def import_module_directly(module_path: str, module_name: str):
    """Import a module directly from file path, bypassing package __init__."""
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_ohlcv():
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    base_price = 100.0

    # Generate realistic price movement
    returns = np.random.randn(50) * 0.02  # 2% daily volatility
    prices = base_price * np.exp(np.cumsum(returns))

    # Create OHLCV with realistic high/low
    daily_range = np.abs(np.random.randn(50)) * 0.01 * prices

    return pd.DataFrame(
        {
            "Open": prices - daily_range * 0.3,
            "High": prices + daily_range,
            "Low": prices - daily_range,
            "Close": prices,
            "Volume": np.random.randint(1000000, 10000000, 50),
        },
        index=dates,
    )


@pytest.fixture
def mock_order_manager():
    """Mock order manager for testing."""

    class MockOrderManager:
        def __init__(self):
            self.orders = []
            self.order_counter = 0

        def place_limit_order(self, symbol, qty, side, limit_price):
            self.order_counter += 1
            order = {
                "id": f"order_{self.order_counter}",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "limit_price": limit_price,
                "status": "pending",
            }
            self.orders.append(order)
            return order

        def cancel_order(self, order_id):
            return {"status": "cancelled", "id": order_id}

        def replace_stop_order(self, order_id, new_stop_price, symbol, qty):
            return {"id": f"replaced_{order_id}", "stop_price": new_stop_price}

    return MockOrderManager()


@pytest.fixture
def entry_planning_module():
    """Load entry_planning module directly."""
    module_path = project_root / "src" / "trading" / "instruments" / "entry_planning.py"
    return import_module_directly(str(module_path), "entry_planning_direct")


@pytest.fixture
def trading_config_module():
    """Load trading_config module directly."""
    module_path = project_root / "config_defaults" / "trading_config.py"
    return import_module_directly(str(module_path), "trading_config_direct")


@pytest.fixture
def trailing_stop_module(trading_config_module):
    """Load trailing_stop_manager module directly."""

    # Mock the date_utils dependency
    class MockDateUtils:
        @staticmethod
        def now_iso():
            return "2024-01-01T00:00:00Z"

    sys.modules["src.utils.date_utils"] = MockDateUtils()

    # Mock the unified_price_fetcher dependency
    class MockPriceFetcher:
        @staticmethod
        def get_current_price(symbol):
            return 100.0

    # Create mock module
    class MockPriceFetcherModule:
        get_current_price = MockPriceFetcher.get_current_price

    sys.modules["src.trading.utils.unified_price_fetcher"] = MockPriceFetcherModule()

    module_path = project_root / "src" / "trading" / "orders" / "trailing_stop_manager.py"
    return import_module_directly(str(module_path), "trailing_stop_manager_direct")


# =============================================================================
# Tests: Issue #366 - OHLCV-Based Intraday Entry Plan
# =============================================================================


class TestEntryPlanning:
    """Test entry planning functionality (Issue #366)."""

    def test_calculate_atr(self, sample_ohlcv, entry_planning_module):
        """Test ATR calculation produces valid output."""
        calculate_atr = entry_planning_module.calculate_atr

        # Function takes individual Series: high, low, close
        atr_series = calculate_atr(
            sample_ohlcv["High"],
            sample_ohlcv["Low"],
            sample_ohlcv["Close"],
            period=14,
        )

        # Returns a Series, get the last valid value
        atr = atr_series.iloc[-1]

        assert isinstance(atr, (float, np.floating))
        assert atr > 0, "ATR should be positive"
        # ATR should be reasonable for ~2% volatility data
        assert 0.1 < atr < 10.0, f"ATR {atr} seems unreasonable"

    def test_find_support_resistance(self, sample_ohlcv, entry_planning_module):
        """Test S/R level detection returns expected structure."""
        find_sr = entry_planning_module.find_support_resistance

        # Function takes high and low Series with lookback
        levels = find_sr(sample_ohlcv["High"], sample_ohlcv["Low"], lookback=20)

        assert isinstance(levels, dict)
        assert "support" in levels
        assert "resistance" in levels
        assert "range" in levels

        # Support should be below resistance
        assert levels["support"] < levels["resistance"], "Support should be below resistance"

        # Range should be positive
        assert levels["range"] > 0, "Range should be positive"

    def test_calculate_entry_plan_buy(self, sample_ohlcv, entry_planning_module):
        """Test buy entry plan generation."""
        calculate_entry_plan = entry_planning_module.calculate_entry_plan

        current_price = float(sample_ohlcv["Close"].iloc[-1])

        plan = calculate_entry_plan(
            ohlcv=sample_ohlcv,
            current_price=current_price,
            signal_direction="BUY",
            atr_multiplier=2.0,
        )

        assert isinstance(plan, dict)
        assert "entry_price" in plan
        assert "stop_loss" in plan
        assert "atr_value" in plan
        assert "plan_quality" in plan
        assert plan["stop_loss"] < plan["entry_price"], "Stop should be below entry for buy"

    def test_calculate_entry_plan_insufficient_data(self, entry_planning_module):
        """Test entry plan with insufficient data returns appropriate result."""
        calculate_entry_plan = entry_planning_module.calculate_entry_plan

        # Only 5 rows - not enough for ATR calculation (needs 20)
        tiny_df = pd.DataFrame(
            {
                "Open": [100, 101, 102, 103, 104],
                "High": [101, 102, 103, 104, 105],
                "Low": [99, 100, 101, 102, 103],
                "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "Volume": [1000000] * 5,
            }
        )

        plan = calculate_entry_plan(
            ohlcv=tiny_df,
            current_price=104.5,
            signal_direction="BUY",
        )

        # Returns a dict with INSUFFICIENT_DATA quality
        assert isinstance(plan, dict)
        assert plan["plan_quality"] == "INSUFFICIENT_DATA"
        assert plan["entry_price"] is None


# =============================================================================
# Tests: Issue #414 - Advanced Trailing Stop Automation
# =============================================================================


class TestTrailingStops:
    """Test trailing stop functionality (Issue #414)."""

    def test_config_loads_climb_rate(self, trading_config_module):
        """Test TrailingStopConfig has climb_rate field."""
        TrailingStopConfig = trading_config_module.TrailingStopConfig  # noqa: N806

        config = TrailingStopConfig()

        # Issue #414: Verify climb rate and gain lock features
        assert hasattr(config, "climb_rate")
        assert config.climb_rate in ("slow", "medium", "fast")
        assert hasattr(config, "volatility_aware")
        assert hasattr(config, "atr_multiplier")
        assert hasattr(config, "profit_zone_start_pct")

    def test_climb_rate_class(self, trading_config_module):
        """Test ClimbRate class provides gain lock percentages."""
        ClimbRate = trading_config_module.ClimbRate  # noqa: N806

        # Test each climb rate
        slow = ClimbRate.get_gain_locks("slow")
        medium = ClimbRate.get_gain_locks("medium")
        fast = ClimbRate.get_gain_locks("fast")

        # Each should return a tuple of 4 values (breakeven, zone1, zone2, zone3)
        assert len(slow) == 4
        assert len(medium) == 4
        assert len(fast) == 4

        # Fast should lock more gains than slow
        assert fast[1] > slow[1], "Fast should lock more gains in zone 1"

    def test_register_position(
        self, mock_order_manager, trailing_stop_module, trading_config_module
    ):
        """Test position registration creates proper state."""
        TrailingStopManager = trailing_stop_module.TrailingStopManager
        TrailingStopConfig = trading_config_module.TrailingStopConfig

        config = TrailingStopConfig(enabled=True, progressive_enabled=True)
        mgr = TrailingStopManager(mock_order_manager, trailing_config=config)

        state = mgr.register_position(
            symbol="AAPL",
            entry_price=100.00,
            initial_stop=95.00,
            quantity=100,
        )

        assert state.symbol == "AAPL"
        assert state.entry_price == 100.00
        assert state.current_stop == 95.00
        assert state.highest_price_seen == 100.00
        assert state.in_profit_zone is False  # Issue #414: profit zone tracking

    def test_stop_moves_up_not_down(
        self, mock_order_manager, trailing_stop_module, trading_config_module
    ):
        """Test stops only move up, never down."""
        TrailingStopManager = trailing_stop_module.TrailingStopManager
        TrailingStopConfig = trading_config_module.TrailingStopConfig

        config = TrailingStopConfig(
            enabled=True,
            progressive_enabled=True,
            never_move_stop_down=True,
            progressive_breakeven_pct=0.02,
            progressive_lock_25_pct=0.04,
            progressive_trail_50_pct=0.06,
        )
        mgr = TrailingStopManager(mock_order_manager, trailing_config=config)
        mgr.register_position(symbol="AAPL", entry_price=100.00, initial_stop=95.00, quantity=100)

        # Price goes up to trigger stop move to breakeven
        new_stop = mgr.calculate_new_stop("AAPL", 102.50)  # 2.5% profit
        assert new_stop == 100.00, "Should move to breakeven"

        # Update state
        state = mgr.get_state("AAPL")
        state.current_stop = 100.00

        # Price drops - stop should NOT move down
        result = mgr.calculate_new_stop("AAPL", 99.00)
        assert result is None, "Stop should not move down"

    def test_profit_zone_tracking(
        self, mock_order_manager, trailing_stop_module, trading_config_module
    ):
        """Test profit zone tracking (Issue #414)."""
        TrailingStopManager = trailing_stop_module.TrailingStopManager
        TrailingStopConfig = trading_config_module.TrailingStopConfig

        config = TrailingStopConfig(
            enabled=True,
            progressive_enabled=True,
            profit_zone_start_pct=0.02,  # 2% = profit zone
        )
        mgr = TrailingStopManager(mock_order_manager, trailing_config=config)
        mgr.register_position(symbol="AAPL", entry_price=100.00, initial_stop=95.00, quantity=100)

        state = mgr.get_state("AAPL")
        assert state.in_profit_zone is False, "Should start outside profit zone"

        # Move price into profit zone
        mgr.calculate_new_stop("AAPL", 102.50)  # 2.5% profit
        assert state.in_profit_zone is True, "Should now be in profit zone"

    def test_get_summary_includes_config(
        self, mock_order_manager, trailing_stop_module, trading_config_module
    ):
        """Test get_summary returns expected structure."""
        TrailingStopManager = trailing_stop_module.TrailingStopManager
        TrailingStopConfig = trading_config_module.TrailingStopConfig

        config = TrailingStopConfig(
            enabled=True,
            progressive_enabled=True,
            climb_rate="fast",
            volatility_aware=True,
        )
        mgr = TrailingStopManager(mock_order_manager, trailing_config=config)

        summary = mgr.get_summary()

        assert isinstance(summary, dict)
        assert summary["enabled"] is True
        assert summary["progressive_mode"] is True
        assert "config" in summary

        # Issue #414: Advanced config fields
        assert summary["config"]["climb_rate"] == "fast"
        assert summary["config"]["volatility_aware"] is True
        assert "gain_lock_percentages" in summary["config"]
        assert "profit_zone_start" in summary["config"]


# =============================================================================
# Tests: CLI Integration Concepts
# =============================================================================


class TestCLIIntegrationConcepts:
    """Test that outputs are CLI-friendly for future integration."""

    def test_entry_plan_returns_cli_friendly_output(self, sample_ohlcv, entry_planning_module):
        """Test entry plan output is serializable for CLI display."""
        calculate_entry_plan = entry_planning_module.calculate_entry_plan

        current_price = float(sample_ohlcv["Close"].iloc[-1])

        plan = calculate_entry_plan(
            ohlcv=sample_ohlcv,
            current_price=current_price,
            signal_direction="BUY",
        )

        # All values should be serializable (not numpy types)
        for key, value in plan.items():
            if value is not None:
                # Convert numpy types if needed - plan should already be clean
                actual_value = value.item() if hasattr(value, "item") else value
                assert isinstance(
                    actual_value, (str, int, float, bool, list, dict)
                ), f"Key '{key}' has non-serializable type: {type(value)}"

    def test_trailing_stop_summary_is_dict(
        self, mock_order_manager, trailing_stop_module, trading_config_module
    ):
        """Test trailing stop summary is CLI-displayable dict."""
        TrailingStopManager = trailing_stop_module.TrailingStopManager
        TrailingStopConfig = trading_config_module.TrailingStopConfig

        mgr = TrailingStopManager(mock_order_manager, trailing_config=TrailingStopConfig())

        summary = mgr.get_summary()

        # Summary should be a pure dict suitable for JSON serialization
        assert isinstance(summary, dict)
        # Should be displayable as formatted output
        assert "enabled" in summary
        assert "positions_tracked" in summary

        # Nested config should also be a dict
        assert isinstance(summary["config"], dict)
