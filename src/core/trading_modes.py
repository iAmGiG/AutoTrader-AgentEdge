#!/usr/bin/env python3
"""
Trading Modes Manager - Configurable Risk Profiles

Issue #400: Trading Modes Configuration System

Provides preset trading modes (Conservative, Moderate, Aggressive) with
externalized YAML configuration. Modes control position sizing, stop losses,
profit targets, and trailing stop parameters.

Future phases:
- Phase 2: Per-ticker configuration overrides
- Phase 3: LLM reasoning for mode selection
- Phase 4: Options support + multimodal input
"""

import logging
import os
import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


class TradingMode(Enum):
    """Available trading modes with different risk profiles."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"

    @classmethod
    def from_string(cls, value: str) -> "TradingMode":
        """Convert string to TradingMode enum."""
        value_lower = value.lower()
        for mode in cls:
            if mode.value == value_lower:
                return mode
        raise ValueError(f"Unknown trading mode: {value}. Valid: {[m.value for m in cls]}")


@dataclass
class ModeParameters:
    """
    Parameters for a trading mode.

    Issue #414: Extended with advanced trailing stop parameters.
    Issue #248: Extended with partial exit parameters.
    """

    mode: TradingMode
    description: str

    # Position sizing
    max_position_pct: float
    max_position_value: float
    max_portfolio_pct: float
    max_positions: int

    # Exit strategy
    stop_loss: float
    take_profit: float

    # Trailing stops (base)
    trailing_enabled: bool
    progressive_enabled: bool
    progressive_breakeven_pct: float
    progressive_lock_25_pct: float
    progressive_trail_50_pct: float
    min_update_interval_seconds: int

    # Issue #414: Advanced trailing stop parameters
    climb_rate: str = "medium"  # slow | medium | fast
    volatility_aware: bool = False
    atr_multiplier: float = 1.5
    profit_zone_start_pct: float = 0.02

    # Risk metrics
    risk_per_trade: float = 0.02
    min_confidence: float = 0.65

    # Issue #248: Partial exit parameters
    partial_exits_enabled: bool = True
    partial_exit_targets: int = 2
    partial_exit_split: list = None  # Will be [0.5, 0.5] by default
    partial_exit_target_1_pct: float = 0.04  # First exit at 4% profit
    partial_exit_target_2_type: str = "trailing"  # "trailing" or "limit"

    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.partial_exit_split is None:
            self.partial_exit_split = [0.5, 0.5]


class TradingModeManager:
    """
    Manages trading mode configuration and parameter access.

    Loads mode configurations from YAML and provides parameters
    to position sizing, stop management, and risk calculations.
    """

    def __init__(self, config_file: Optional[str] = None, mode: Optional[TradingMode] = None):
        """
        Initialize trading mode manager.

        Args:
            config_file: Path to trading_modes.yaml (default: config_defaults/)
            mode: Initial trading mode (default: from config or MODERATE)
        """
        if yaml is None:
            raise ImportError("PyYAML required. Install with: pip install pyyaml")

        if config_file is None:
            config_dir = os.path.join(os.path.dirname(__file__), "../../config_defaults")
            config_file = os.path.join(config_dir, "trading_modes.yaml")

        self.config_file = config_file
        self._config = self._load_config()

        # SQLite database for persisting current mode (Issue #434 Phase 1)
        db_dir = os.path.join(os.path.dirname(__file__), "../../state")
        os.makedirs(db_dir, exist_ok=True)
        self._db_path = os.path.join(db_dir, "user.db")
        self._init_database()

        # Load persisted mode or use provided/default
        self._current_mode = mode or self._load_persisted_mode() or self._get_default_mode()
        self._mode_cache: Dict[TradingMode, ModeParameters] = {}

        logger.info(f"TradingModeManager initialized: mode={self._current_mode.value}")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_file):
            logger.warning(f"Config file not found: {self.config_file}, using defaults")
            return self._get_default_config()

        with open(self.config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            logger.debug(f"Loaded trading modes config from {self.config_file}")
            return config

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file not found."""
        return {
            "default_mode": "moderate",
            "modes": {
                "conservative": {
                    "description": "Low risk, capital preservation focus",
                    "max_position_pct": 0.05,
                    "max_position_value": 2500,
                    "max_portfolio_pct": 0.10,
                    "max_positions": 5,
                    "stop_loss": 0.02,
                    "take_profit": 0.05,
                    "trailing_stops": {
                        "enabled": True,
                        "progressive_enabled": True,
                        "progressive_breakeven_pct": 0.02,
                        "progressive_lock_25_pct": 0.03,
                        "progressive_trail_50_pct": 0.04,
                        "min_update_interval_seconds": 60,
                    },
                    "risk_per_trade": 0.01,
                    "min_confidence": 0.75,
                },
                "moderate": {
                    "description": "Balanced risk/reward for steady growth",
                    "max_position_pct": 0.10,
                    "max_position_value": 5000,
                    "max_portfolio_pct": 0.20,
                    "max_positions": 10,
                    "stop_loss": 0.05,
                    "take_profit": 0.10,
                    "trailing_stops": {
                        "enabled": True,
                        "progressive_enabled": True,
                        "progressive_breakeven_pct": 0.02,
                        "progressive_lock_25_pct": 0.04,
                        "progressive_trail_50_pct": 0.06,
                        "min_update_interval_seconds": 60,
                    },
                    "risk_per_trade": 0.02,
                    "min_confidence": 0.65,
                },
                "aggressive": {
                    "description": "Higher risk for maximum growth potential",
                    "max_position_pct": 0.20,
                    "max_position_value": 10000,
                    "max_portfolio_pct": 0.40,
                    "max_positions": 15,
                    "stop_loss": 0.08,
                    "take_profit": 0.20,
                    "trailing_stops": {
                        "enabled": True,
                        "progressive_enabled": True,
                        "progressive_breakeven_pct": 0.03,
                        "progressive_lock_25_pct": 0.06,
                        "progressive_trail_50_pct": 0.10,
                        "min_update_interval_seconds": 30,
                    },
                    "risk_per_trade": 0.03,
                    "min_confidence": 0.55,
                },
            },
        }

    def _get_default_mode(self) -> TradingMode:
        """Get default mode from config."""
        default_str = self._config.get("default_mode", "moderate")
        return TradingMode.from_string(default_str)

    def _init_database(self) -> None:
        """Initialize SQLite database with trading_mode_history table."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trading_mode_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    symbol TEXT,
                    reason TEXT,
                    session_id TEXT
                )
            """
            )
            conn.commit()
            conn.close()
            logger.debug(f"Initialized user.db at {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def _load_persisted_mode(self) -> Optional[TradingMode]:
        """Load most recent trading mode from database."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT mode FROM trading_mode_history
                WHERE symbol IS NULL
                ORDER BY timestamp DESC LIMIT 1
            """
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                mode_str = row[0]
                logger.debug(f"Loaded persisted mode: {mode_str}")
                return TradingMode.from_string(mode_str)
        except Exception as e:
            logger.warning(f"Failed to load persisted mode: {e}")
        return None

    def _save_persisted_mode(
        self, mode: TradingMode, symbol: Optional[str] = None, reason: str = "user_change"
    ) -> None:
        """Save trading mode change to database history."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trading_mode_history (timestamp, mode, symbol, reason)
                VALUES (?, ?, ?, ?)
            """,
                (now_iso(), mode.value, symbol, reason),
            )
            conn.commit()
            conn.close()
            logger.debug(f"Persisted mode: {mode.value} (symbol={symbol}, reason={reason})")
        except Exception as e:
            logger.error(f"Failed to persist mode: {e}")

    @property
    def current_mode(self) -> TradingMode:
        """Get current trading mode."""
        return self._current_mode

    def set_mode(self, mode: TradingMode) -> None:
        """
        Set current trading mode and persist to disk.

        Args:
            mode: New trading mode
        """
        old_mode = self._current_mode
        self._current_mode = mode
        self._save_persisted_mode(mode)
        logger.info(f"Trading mode changed: {old_mode.value} -> {mode.value}")

    def get_parameters(self, mode: Optional[TradingMode] = None) -> ModeParameters:
        """
        Get parameters for a trading mode.

        Args:
            mode: Trading mode (default: current mode)

        Returns:
            ModeParameters dataclass with all mode settings
        """
        mode = mode or self._current_mode

        # Check cache
        if mode in self._mode_cache:
            return self._mode_cache[mode]

        # Build from config
        mode_config = self._config["modes"].get(mode.value, {})
        trailing = mode_config.get("trailing_stops", {})
        partial_exits = mode_config.get("partial_exits", {})

        params = ModeParameters(
            mode=mode,
            description=mode_config.get("description", ""),
            max_position_pct=mode_config.get("max_position_pct", 0.10),
            max_position_value=mode_config.get("max_position_value", 5000),
            max_portfolio_pct=mode_config.get("max_portfolio_pct", 0.20),
            max_positions=mode_config.get("max_positions", 10),
            stop_loss=mode_config.get("stop_loss", 0.05),
            take_profit=mode_config.get("take_profit", 0.10),
            trailing_enabled=trailing.get("enabled", True),
            progressive_enabled=trailing.get("progressive_enabled", True),
            progressive_breakeven_pct=trailing.get("progressive_breakeven_pct", 0.02),
            progressive_lock_25_pct=trailing.get("progressive_lock_25_pct", 0.04),
            progressive_trail_50_pct=trailing.get("progressive_trail_50_pct", 0.06),
            min_update_interval_seconds=trailing.get("min_update_interval_seconds", 60),
            # Issue #414: Advanced trailing stop parameters
            climb_rate=trailing.get("climb_rate", "medium"),
            volatility_aware=trailing.get("volatility_aware", False),
            atr_multiplier=trailing.get("atr_multiplier", 1.5),
            profit_zone_start_pct=trailing.get("profit_zone_start_pct", 0.02),
            risk_per_trade=mode_config.get("risk_per_trade", 0.02),
            min_confidence=mode_config.get("min_confidence", 0.65),
            # Issue #248: Partial exit parameters
            partial_exits_enabled=partial_exits.get("enabled", True),
            partial_exit_targets=partial_exits.get("targets", 2),
            partial_exit_split=partial_exits.get("split", [0.5, 0.5]),
            partial_exit_target_1_pct=partial_exits.get("target_1_pct", 0.04),
            partial_exit_target_2_type=partial_exits.get("target_2", "trailing"),
        )

        self._mode_cache[mode] = params
        return params

    def get_trailing_stop_config_dict(self, mode: Optional[TradingMode] = None) -> Dict[str, Any]:
        """
        Get trailing stop configuration as dict for TrailingStopConfig.

        Args:
            mode: Trading mode (default: current mode)

        Returns:
            Dict compatible with TrailingStopConfig initialization
        """
        params = self.get_parameters(mode)
        return {
            "enabled": params.trailing_enabled,
            "progressive_enabled": params.progressive_enabled,
            "progressive_breakeven_pct": params.progressive_breakeven_pct,
            "progressive_lock_25_pct": params.progressive_lock_25_pct,
            "progressive_trail_50_pct": params.progressive_trail_50_pct,
            "min_update_interval_seconds": params.min_update_interval_seconds,
            "never_move_stop_down": True,
            # Issue #414: Advanced features
            "climb_rate": params.climb_rate,
            "volatility_aware": params.volatility_aware,
            "atr_multiplier": params.atr_multiplier,
            "profit_zone_start_pct": params.profit_zone_start_pct,
        }

    def get_risk_config_dict(self, mode: Optional[TradingMode] = None) -> Dict[str, Any]:
        """
        Get risk management configuration as dict.

        Args:
            mode: Trading mode (default: current mode)

        Returns:
            Dict with risk management parameters
        """
        params = self.get_parameters(mode)
        return {
            "max_position_pct": params.max_position_pct,
            "max_position_value": params.max_position_value,
            "max_portfolio_pct": params.max_portfolio_pct,
            "max_positions": params.max_positions,
            "risk_per_trade": params.risk_per_trade,
            "min_confidence": params.min_confidence,
            "stop_loss": params.stop_loss,
            "take_profit": params.take_profit,
        }

    def get_partial_exit_config_dict(self, mode: Optional[TradingMode] = None) -> Dict[str, Any]:
        """
        Get partial exit configuration as dict for PartialExitManager.

        Args:
            mode: Trading mode (default: current mode)

        Returns:
            Dict compatible with PartialExitManager initialization

        Issue #248: Partial Position Exits
        """
        params = self.get_parameters(mode)
        return {
            "enabled": params.partial_exits_enabled,
            "targets": params.partial_exit_targets,
            "split": params.partial_exit_split,
            "target_1_pct": params.partial_exit_target_1_pct,
            "target_2": params.partial_exit_target_2_type,
        }

    def get_all_modes(self) -> Dict[str, ModeParameters]:
        """Get parameters for all available modes."""
        return {mode.value: self.get_parameters(mode) for mode in TradingMode}

    def reload_config(self) -> None:
        """Reload configuration from file."""
        self._config = self._load_config()
        self._mode_cache.clear()
        logger.info("Trading modes configuration reloaded")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current mode and key parameters."""
        params = self.get_parameters()
        return {
            "current_mode": self._current_mode.value,
            "description": params.description,
            "position_size_pct": f"{params.max_position_pct:.0%}",
            "max_position_value": f"${params.max_position_value:,.0f}",
            "stop_loss": f"{params.stop_loss:.0%}",
            "take_profit": f"{params.take_profit:.0%}",
            "trailing_stops": params.trailing_enabled,
        }


# Global instance for easy access
_mode_manager: Optional[TradingModeManager] = None


def get_mode_manager() -> TradingModeManager:
    """Get global trading mode manager instance."""
    global _mode_manager
    if _mode_manager is None:
        _mode_manager = TradingModeManager()
    return _mode_manager


def set_trading_mode(mode: TradingMode) -> None:
    """Set global trading mode."""
    get_mode_manager().set_mode(mode)


def get_current_mode() -> TradingMode:
    """Get current global trading mode."""
    return get_mode_manager().current_mode


def get_mode_parameters(mode: Optional[TradingMode] = None) -> ModeParameters:
    """Get parameters for a trading mode."""
    return get_mode_manager().get_parameters(mode)
