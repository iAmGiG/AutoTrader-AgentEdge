"""
Trading Configuration Management
Centralized configuration for all trading parameters.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class MACDConfig:
    """MACD indicator configuration."""

    fast: int = 13
    slow: int = 34
    signal: int = 8


@dataclass
class RSIConfig:
    """RSI indicator configuration."""

    period: int = 14
    oversold: int = 30
    overbought: int = 70


@dataclass
class TimeframeConfig:
    """Timeframe configuration for multi-timeframe analysis."""

    default: str = "1d"
    enabled_timeframes: list = None

    def __post_init__(self):
        """Initialize default enabled timeframes."""
        if self.enabled_timeframes is None:
            # Standard timeframes from minute to monthly
            self.enabled_timeframes = [
                "1m",  # 1 minute - scalping
                "5m",  # 5 minutes - fast intraday
                "15m",  # 15 minutes - intraday
                "30m",  # 30 minutes - intraday swing
                "1h",  # 1 hour - medium-term
                "2h",  # 2 hours - swing
                "4h",  # 4 hours - swing/position
                "1d",  # 1 day - position trading
                "1w",  # 1 week - intermediate-term
                "1M",  # 1 month - long-term
            ]

    def is_valid(self, timeframe: str) -> bool:
        """Check if a timeframe is valid."""
        return timeframe in self.enabled_timeframes

    def validate(self) -> bool:
        """Validate timeframe configuration."""
        # Check default is in enabled timeframes
        if self.default not in self.enabled_timeframes:
            return False
        # Check at least one timeframe is enabled
        if not self.enabled_timeframes or len(self.enabled_timeframes) == 0:
            return False
        return True


@dataclass
class ExitConfig:
    """Exit strategy configuration."""

    take_profit: float
    stop_loss: float
    description: str
    expected_value_50wr: float
    breakeven_win_rate: float


class ClimbRate:
    """
    Climb rate presets for trailing stop aggressiveness.

    Issue #414: Advanced Trailing Stop Automation

    Climb rate affects how quickly stops move up as price increases:
    - slow: Conservative, locks smaller gains (20%/40%/60%)
    - medium: Balanced, standard gain locking (25%/50%/75%)
    - fast: Aggressive, locks larger gains quickly (33%/60%/80%)
    """

    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"

    # Gain lock percentages by climb rate
    # Format: (breakeven_zone, lock_zone_1, lock_zone_2)
    GAIN_LOCK_PERCENTAGES = {
        "slow": (0.0, 0.20, 0.40, 0.60),  # Breakeven, 20%, 40%, 60% trail
        "medium": (0.0, 0.25, 0.50, 0.75),  # Breakeven, 25%, 50%, 75% trail
        "fast": (0.0, 0.33, 0.60, 0.80),  # Breakeven, 33%, 60%, 80% trail
    }

    @classmethod
    def get_gain_locks(cls, rate: str) -> tuple:
        """Get gain lock percentages for a climb rate."""
        return cls.GAIN_LOCK_PERCENTAGES.get(rate, cls.GAIN_LOCK_PERCENTAGES["medium"])


@dataclass
class TrailingStopConfig:
    """
    Trailing stop configuration for dynamic stop management.

    Issue #414: Advanced Trailing Stop Automation - KILLER FEATURE

    Enhanced with:
    - Configurable climb rates (slow/medium/fast)
    - Volatility-aware adjustments via ATR
    - Profit-zone awareness with configurable thresholds
    """

    enabled: bool = True
    # Profit thresholds (as decimal, e.g., 0.02 = 2%)
    breakeven_trigger: float = 0.005  # Move to breakeven at 0.5% profit
    trail_start_trigger: float = 0.01  # Start trailing at 1% profit
    # Trail distances
    trail_distance: float = 0.005  # Trail by 0.5% below price
    # Progressive stops (from existing adjust_stop logic)
    progressive_enabled: bool = True
    progressive_breakeven_pct: float = 0.02  # Move to breakeven at 2%
    progressive_lock_25_pct: float = 0.04  # Lock 25% of gains at 4%
    progressive_trail_50_pct: float = 0.06  # Trail 50% of gains at 6%+
    # Rate limiting
    min_update_interval_seconds: int = 60  # Don't update more than once per minute
    # Safety
    never_move_stop_down: bool = True  # Stops only move up, never down

    # === Issue #414: Advanced Trailing Stop Features ===
    # Climb rate: slow | medium | fast - controls how aggressively stops climb
    climb_rate: str = "medium"
    # Volatility awareness: adjust trail distance based on ATR
    volatility_aware: bool = False
    # ATR multiplier for volatility-based trailing (higher = wider stops)
    atr_multiplier: float = 1.5
    # ATR period for volatility calculation
    atr_period: int = 14
    # Profit zone start: when to enter "profit protection" mode
    profit_zone_start_pct: float = 0.02  # 2% = in profit zone

    def get_gain_lock_percentages(self) -> tuple:
        """Get gain lock percentages based on climb rate."""
        return ClimbRate.get_gain_locks(self.climb_rate)


class TradingConfig:
    """
    Trading configuration manager.

    Benefits of configuration system:
    1. Easy parameter tuning without code changes
    2. A/B testing different configurations
    3. Environment-specific settings (dev/test/prod)
    4. Audit trail of parameter changes
    5. Consistent configuration across all components
    """

    def __init__(self, config_file: str = None):
        """Load configuration from file or use defaults."""
        if config_file is None:
            config_path = os.path.dirname(__file__)
            # Try YAML first, fallback to JSON
            yaml_file = os.path.join(config_path, "trading_config.yaml")
            json_file = os.path.join(config_path, "trading_config.json")

            if os.path.exists(yaml_file):
                config_file = yaml_file
            elif os.path.exists(json_file):
                config_file = json_file
            else:
                config_file = yaml_file  # Default to YAML for new installs

        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from YAML or JSON file."""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r", encoding="utf-8") as f:
                if self.config_file.endswith(".yaml") or self.config_file.endswith(".yml"):
                    if yaml is None:
                        raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
                    return yaml.safe_load(f)
                else:
                    return json.load(f)
        else:
            # Return default configuration
            return self._get_default_config()

    def _get_default_config(self) -> Dict:
        """Get default configuration."""
        return {
            "strategy_parameters": {
                "macd": {"fast": 13, "slow": 34, "signal": 8},
                "rsi": {"period": 14, "oversold": 30, "overbought": 70},
                "timeframe": {
                    "default": "1d",
                    "enabled_timeframes": [
                        "1m",
                        "5m",
                        "15m",
                        "30m",
                        "1h",
                        "2h",
                        "4h",
                        "1d",
                        "1w",
                        "1M",
                    ],
                },
                "exits": {
                    "balanced": {
                        "take_profit": 0.08,
                        "stop_loss": 0.05,
                        "expected_value_50wr": 0.015,
                        "breakeven_win_rate": 0.385,
                    },
                    "default": "balanced",
                },
            },
            "risk_management": {
                "max_position_pct": 0.15,
                "max_position_value": 5000,
                "max_portfolio_pct": 0.20,
                "max_positions": 10,
                "risk_per_trade": 0.02,
                "min_confidence": 0.65,
                "risk_free_rate": 0.02,
            },
        }

    def get_macd_config(self) -> MACDConfig:
        """Get MACD configuration."""
        params = self.config["strategy_parameters"]["macd"]
        return MACDConfig(fast=params["fast"], slow=params["slow"], signal=params["signal"])

    def get_rsi_config(self) -> RSIConfig:
        """Get RSI configuration."""
        params = self.config["strategy_parameters"]["rsi"]
        return RSIConfig(
            period=params["period"], oversold=params["oversold"], overbought=params["overbought"]
        )

    def get_timeframe_config(self) -> TimeframeConfig:
        """Get timeframe configuration."""
        params = self.config.get("strategy_parameters", {}).get("timeframe", {})
        return TimeframeConfig(
            default=params.get("default", "1d"),
            enabled_timeframes=params.get("enabled_timeframes", None),
        )

    def get_exit_config(self, strategy: str = None) -> ExitConfig:
        """Get exit strategy configuration."""
        exits = self.config["strategy_parameters"]["exits"]

        if strategy is None:
            strategy = exits.get("default", "balanced")

        if strategy not in exits:
            strategy = "balanced"  # Fallback to balanced

        params = exits[strategy]
        return ExitConfig(
            take_profit=params["take_profit"],
            stop_loss=params["stop_loss"],
            description=params.get("description", ""),
            expected_value_50wr=params.get("expected_value_50wr", 0),
            breakeven_win_rate=params.get("breakeven_win_rate", 0.5),
        )

    def update_config(self, section: str, key: str, value: Any):
        """Update configuration value."""
        if section in self.config:
            self.config[section][key] = value
            self._save_config()

    def _save_config(self):
        """Save configuration to file."""
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_all_exit_strategies(self) -> Dict[str, ExitConfig]:
        """Get all available exit strategies."""
        exits = self.config["strategy_parameters"]["exits"]
        strategies = {}

        for name, params in exits.items():
            if name != "default" and isinstance(params, dict):
                strategies[name] = ExitConfig(
                    take_profit=params["take_profit"],
                    stop_loss=params["stop_loss"],
                    description=params.get("description", ""),
                    expected_value_50wr=params.get("expected_value_50wr", 0),
                    breakeven_win_rate=params.get("breakeven_win_rate", 0.5),
                )

        return strategies

    def get_risk_config(self, key: str = None) -> Any:
        """
        Get risk management configuration.

        Args:
            key: Specific risk parameter (e.g., 'max_position_pct', 'stop_loss')
                 If None, returns entire risk_management dict

        Returns:
            Risk parameter value or entire risk config dict
        """
        risk_config = self.config.get("risk_management", {})

        # Fallback to default if not in config
        if not risk_config:
            risk_config = self._get_default_config()["risk_management"]

        if key is None:
            return risk_config

        # Also check in exits for backward compatibility
        if key in ["stop_loss", "take_profit"]:
            exit_config = self.get_exit_config()
            if key == "stop_loss":
                return exit_config.stop_loss
            elif key == "take_profit":
                return exit_config.take_profit

        return risk_config.get(key)

    def get_trailing_stop_config(self) -> TrailingStopConfig:
        """
        Get trailing stop configuration.

        Returns:
            TrailingStopConfig with all trailing stop parameters
        """
        trailing_config = self.config.get("trailing_stops", {})

        return TrailingStopConfig(
            enabled=trailing_config.get("enabled", True),
            breakeven_trigger=trailing_config.get("breakeven_trigger", 0.005),
            trail_start_trigger=trailing_config.get("trail_start_trigger", 0.01),
            trail_distance=trailing_config.get("trail_distance", 0.005),
            progressive_enabled=trailing_config.get("progressive_enabled", True),
            progressive_breakeven_pct=trailing_config.get("progressive_breakeven_pct", 0.02),
            progressive_lock_25_pct=trailing_config.get("progressive_lock_25_pct", 0.04),
            progressive_trail_50_pct=trailing_config.get("progressive_trail_50_pct", 0.06),
            min_update_interval_seconds=trailing_config.get("min_update_interval_seconds", 60),
            never_move_stop_down=trailing_config.get("never_move_stop_down", True),
            # Issue #414: Advanced features
            climb_rate=trailing_config.get("climb_rate", "medium"),
            volatility_aware=trailing_config.get("volatility_aware", False),
            atr_multiplier=trailing_config.get("atr_multiplier", 1.5),
            atr_period=trailing_config.get("atr_period", 14),
            profit_zone_start_pct=trailing_config.get("profit_zone_start_pct", 0.02),
        )

    def validate_config(self) -> bool:
        """Validate configuration parameters."""
        try:
            macd = self.get_macd_config()
            assert macd.fast > 0 and macd.slow > macd.fast
            assert macd.signal > 0

            rsi = self.get_rsi_config()
            assert 0 < rsi.oversold < rsi.overbought < 100
            assert rsi.period > 0

            timeframe = self.get_timeframe_config()
            assert timeframe.validate(), "Timeframe configuration invalid"

            exits = self.get_all_exit_strategies()
            for name, exit_cfg in exits.items():
                assert 0 < exit_cfg.stop_loss < 1
                assert 0 < exit_cfg.take_profit < 1
                assert 0 <= exit_cfg.breakeven_win_rate <= 1

            return True
        except (KeyError, AssertionError) as e:
            print(f"Configuration validation failed: {e}")
            return False


# Global instance for easy access
_config_instance = None


def get_config() -> TradingConfig:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = TradingConfig()
    return _config_instance


def reload_config(config_file: str = None):
    """Reload configuration from file."""
    global _config_instance
    _config_instance = TradingConfig(config_file)
    return _config_instance
