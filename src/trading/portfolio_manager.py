#!/usr/bin/env python3
"""
Portfolio Manager - Unified Portfolio Risk & Allocation Management

Issue #333: Portfolio Manager Agent - Risk & Position Sizing

Provides:
- Pre-trade risk assessment (buying power, position limits, exposure)
- Portfolio allocation tracking and display
- Integration with PositionSizer (#416), TradingModeManager (#400)
- Existing position detection and warnings
- Sector concentration tracking

Phases:
- Phase 1: Config, buying power, position sizing, allocation display ✓
- Phase 2: Sector limits, correlation analysis
- Phase 3: Volatility-adjusted sizing, rebalancing, tax-loss harvesting
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import yaml

from src.core.trading_modes import TradingMode, TradingModeManager, get_mode_manager
from src.trading.position_sizer import PositionSizer, PositionSizeResult

logger = logging.getLogger(__name__)


class TradeCheckResult(Enum):
    """Result of pre-trade feasibility check."""

    APPROVED = "approved"
    WARNING = "warning"  # Can proceed but with warnings
    BLOCKED = "blocked"  # Cannot proceed


@dataclass
class PortfolioConfig:
    """Portfolio configuration loaded from YAML."""

    # Portfolio settings
    size_usd: Optional[float]
    risk_per_trade_pct: float
    max_position_pct: float
    max_exposure_pct: float

    # Limits
    max_open_positions: int
    max_daily_trades: int
    min_position_usd: float
    max_position_usd: float

    # Sector limits
    sector_limits_enabled: bool
    max_sector_pct: float
    warn_sector_pct: float

    # Warnings
    position_size_warning_pct: float
    exposure_warning_pct: float
    hard_block_on_limits: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PortfolioConfig":
        """Create PortfolioConfig from dictionary."""
        portfolio = data.get("portfolio", {})
        limits = data.get("limits", {})
        sector = data.get("sector_limits", {})
        warnings = data.get("warnings", {})

        return cls(
            size_usd=portfolio.get("size_usd"),
            risk_per_trade_pct=portfolio.get("risk_per_trade_pct", 0.02),
            max_position_pct=portfolio.get("max_position_pct", 0.10),
            max_exposure_pct=portfolio.get("max_exposure_pct", 0.80),
            max_open_positions=limits.get("max_open_positions", 10),
            max_daily_trades=limits.get("max_daily_trades", 20),
            min_position_usd=limits.get("min_position_usd", 100),
            max_position_usd=limits.get("max_position_usd", 25000),
            sector_limits_enabled=sector.get("enabled", True),
            max_sector_pct=sector.get("max_sector_pct", 0.40),
            warn_sector_pct=sector.get("warn_sector_pct", 0.30),
            position_size_warning_pct=warnings.get("position_size_warning_pct", 0.08),
            exposure_warning_pct=warnings.get("exposure_warning_pct", 0.70),
            hard_block_on_limits=warnings.get("hard_block_on_limits", False),
        )

    @classmethod
    def default(cls) -> "PortfolioConfig":
        """Create default configuration."""
        return cls.from_dict({})


@dataclass
class TradeAssessment:
    """Pre-trade risk assessment result."""

    symbol: str
    result: TradeCheckResult
    messages: List[str]
    warnings: List[str]

    # Position sizing
    size_result: Optional[PositionSizeResult]

    # Portfolio context
    portfolio_value: float
    buying_power: float
    current_exposure_pct: float
    existing_position_value: float

    # After trade (projected)
    projected_exposure_pct: float
    projected_position_pct: float

    def is_approved(self) -> bool:
        """Check if trade is approved (possibly with warnings)."""
        return self.result in (TradeCheckResult.APPROVED, TradeCheckResult.WARNING)

    def get_summary(self) -> str:
        """Get human-readable summary."""
        lines = []

        # Header
        status_emoji = {
            TradeCheckResult.APPROVED: "✅",
            TradeCheckResult.WARNING: "⚠️",
            TradeCheckResult.BLOCKED: "❌",
        }
        lines.append(f"{status_emoji[self.result]} Trade Assessment: {self.symbol}")
        lines.append("─" * 40)

        # Portfolio context
        lines.append(f"Portfolio Value: ${self.portfolio_value:,.2f}")
        lines.append(f"Buying Power: ${self.buying_power:,.2f}")
        lines.append(f"Current Exposure: {self.current_exposure_pct:.1%}")

        # Existing position
        if self.existing_position_value > 0:
            lines.append(f"⚠️ Existing Position: ${self.existing_position_value:,.2f}")

        lines.append("")

        # Sizing result
        if self.size_result and self.size_result.is_valid:
            lines.append("Suggested Position:")
            lines.append(
                f"  {self.size_result.shares} shares @ ${self.size_result.price_per_share:.2f}"
            )
            lines.append(f"  Value: ${self.size_result.position_value:,.2f}")
            lines.append(f"  Portfolio %: {self.projected_position_pct:.1%}")

        # Warnings
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  ⚠️ {warning}")

        # Block messages
        if self.result == TradeCheckResult.BLOCKED:
            lines.append("")
            lines.append("Blocked:")
            for msg in self.messages:
                lines.append(f"  ❌ {msg}")

        return "\n".join(lines)


class PortfolioManager:
    """
    Unified portfolio management for risk assessment and allocation tracking.

    Issue #333: Portfolio Manager Agent - Risk & Position Sizing

    Integrates:
    - PositionSizer for position sizing calculations (#416)
    - TradingModeManager for profile-based parameters (#400)
    - PositionManager for current holdings (broker positions)
    - ApprovedTickersManager for per-ticker limits (#415)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        mode_manager: Optional[TradingModeManager] = None,
        position_sizer: Optional[PositionSizer] = None,
    ):
        """
        Initialize portfolio manager.

        Args:
            config_path: Path to portfolio_config.yaml
            mode_manager: Trading mode manager (default: global instance)
            position_sizer: Position sizer (default: create new)
        """
        self.config = self._load_config(config_path)
        self.mode_manager = mode_manager or get_mode_manager()
        self.position_sizer = position_sizer or PositionSizer(mode_manager=self.mode_manager)

        # Cache for positions (to be populated from broker)
        self._positions_cache: Dict[str, Dict[str, Any]] = {}
        self._account_cache: Dict[str, Any] = {}

        logger.info("PortfolioManager initialized")

    def _load_config(self, config_path: Optional[str] = None) -> PortfolioConfig:
        """Load configuration from YAML file."""
        if config_path is None:
            config_dir = os.path.join(os.path.dirname(__file__), "../../config_defaults")
            config_path = os.path.join(config_dir, "portfolio_config.yaml")

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                logger.debug(f"Loaded portfolio config from {config_path}")
                return PortfolioConfig.from_dict(data)
        else:
            logger.warning(f"Portfolio config not found at {config_path}, using defaults")
            return PortfolioConfig.default()

    def update_from_broker(
        self,
        positions: Dict[str, Dict[str, Any]],
        account_info: Dict[str, Any],
    ) -> None:
        """
        Update portfolio state from broker data.

        Args:
            positions: Dict of symbol -> position data
            account_info: Account data (equity, buying_power, etc.)
        """
        self._positions_cache = positions
        self._account_cache = account_info
        logger.debug(f"Updated portfolio state: {len(positions)} positions")

    def get_portfolio_value(self) -> float:
        """Get total portfolio value."""
        # Use config override if set, otherwise from broker
        if self.config.size_usd:
            return self.config.size_usd

        return self._account_cache.get("portfolio_value", 0.0)

    def get_buying_power(self) -> float:
        """Get available buying power."""
        return self._account_cache.get("buying_power", 0.0)

    def get_total_exposure(self) -> float:
        """Get total exposure (sum of all position values)."""
        return sum(pos.get("market_value", 0) for pos in self._positions_cache.values())

    def get_exposure_pct(self) -> float:
        """Get current exposure as percentage of portfolio."""
        portfolio_value = self.get_portfolio_value()
        if portfolio_value <= 0:
            return 0.0
        return self.get_total_exposure() / portfolio_value

    def get_position_value(self, symbol: str) -> float:
        """Get current position value for a symbol."""
        position = self._positions_cache.get(symbol)
        return position.get("market_value", 0.0) if position else 0.0

    def has_position(self, symbol: str) -> bool:
        """Check if we have an existing position in this symbol."""
        return symbol in self._positions_cache

    def assess_trade(  # noqa: C901
        self,
        symbol: str,
        current_price: float,
        mode: Optional[TradingMode] = None,
        stop_price: Optional[float] = None,
    ) -> TradeAssessment:
        """
        Perform pre-trade risk assessment.

        Args:
            symbol: Ticker symbol
            current_price: Current market price
            mode: Trading mode override
            stop_price: Stop loss price (optional)

        Returns:
            TradeAssessment with sizing and risk analysis
        """
        portfolio_value = self.get_portfolio_value()
        buying_power = self.get_buying_power()
        existing_value = self.get_position_value(symbol)
        current_exposure = self.get_exposure_pct()

        warnings = []
        block_messages = []

        # Calculate position size
        size_result = self.position_sizer.calculate_position_size(
            symbol=symbol,
            current_price=current_price,
            portfolio_value=portfolio_value,
            buying_power=buying_power,
            existing_position_value=existing_value,
            mode=mode,
            stop_price=stop_price,
        )

        # Check position sizing validity
        if not size_result.is_valid:
            block_messages.append(size_result.validation_message)

        # Calculate projected exposure
        projected_exposure = current_exposure
        projected_position_pct = 0.0
        if size_result.is_valid and portfolio_value > 0:
            projected_position_pct = (existing_value + size_result.position_value) / portfolio_value
            projected_exposure = current_exposure + (size_result.position_value / portfolio_value)

        # Check limits and generate warnings

        # Existing position warning
        if existing_value > 0:
            warnings.append(
                f"Existing position: ${existing_value:,.2f} "
                f"({existing_value / portfolio_value:.1%} of portfolio)"
            )

        # Position size warning
        if projected_position_pct > self.config.position_size_warning_pct:
            warnings.append(
                f"Position would be {projected_position_pct:.1%} of portfolio "
                f"(warning threshold: {self.config.position_size_warning_pct:.0%})"
            )

        # Exposure warning
        if projected_exposure > self.config.exposure_warning_pct:
            warnings.append(
                f"Total exposure would be {projected_exposure:.1%} "
                f"(warning threshold: {self.config.exposure_warning_pct:.0%})"
            )

        # Position count check
        if (
            symbol not in self._positions_cache
            and len(self._positions_cache) >= self.config.max_open_positions
        ):
            msg = f"Would exceed max positions ({self.config.max_open_positions})"
            if self.config.hard_block_on_limits:
                block_messages.append(msg)
            else:
                warnings.append(msg)

        # Max position value check
        if size_result.position_value > self.config.max_position_usd:
            msg = f"Position value ${size_result.position_value:,.0f} exceeds max ${self.config.max_position_usd:,.0f}"
            if self.config.hard_block_on_limits:
                block_messages.append(msg)
            else:
                warnings.append(msg)

        # Max exposure check
        if projected_exposure > self.config.max_exposure_pct:
            msg = f"Would exceed max exposure ({self.config.max_exposure_pct:.0%})"
            if self.config.hard_block_on_limits:
                block_messages.append(msg)
            else:
                warnings.append(msg)

        # Determine result
        if block_messages:
            result = TradeCheckResult.BLOCKED
        elif warnings:
            result = TradeCheckResult.WARNING
        else:
            result = TradeCheckResult.APPROVED

        return TradeAssessment(
            symbol=symbol,
            result=result,
            messages=block_messages,
            warnings=warnings,
            size_result=size_result,
            portfolio_value=portfolio_value,
            buying_power=buying_power,
            current_exposure_pct=current_exposure,
            existing_position_value=existing_value,
            projected_exposure_pct=projected_exposure,
            projected_position_pct=projected_position_pct,
        )

    def get_allocation_summary(self) -> Dict[str, Any]:
        """
        Get current portfolio allocation summary.

        Returns:
            Dict with allocation statistics
        """
        portfolio_value = self.get_portfolio_value()
        positions = []

        for symbol, pos in self._positions_cache.items():
            market_value = pos.get("market_value", 0)
            pct = market_value / portfolio_value if portfolio_value > 0 else 0

            positions.append(
                {
                    "symbol": symbol,
                    "shares": pos.get("qty", 0),
                    "market_value": market_value,
                    "pct_of_portfolio": pct,
                    "unrealized_pl": pos.get("unrealized_pl", 0),
                    "unrealized_pl_pct": pos.get("unrealized_pl_percent", 0),
                }
            )

        # Sort by value descending
        positions.sort(key=lambda p: p["market_value"], reverse=True)

        total_exposure = self.get_total_exposure()
        cash = portfolio_value - total_exposure

        return {
            "portfolio_value": portfolio_value,
            "total_exposure": total_exposure,
            "exposure_pct": self.get_exposure_pct(),
            "cash": cash,
            "cash_pct": cash / portfolio_value if portfolio_value > 0 else 1.0,
            "position_count": len(positions),
            "max_positions": self.config.max_open_positions,
            "positions": positions,
        }

    def format_allocation_display(self) -> str:
        """
        Format allocation for display.

        Returns:
            Human-readable allocation summary
        """
        summary = self.get_allocation_summary()
        lines = []

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 Portfolio Allocation")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"Portfolio Value: ${summary['portfolio_value']:,.2f}")
        lines.append(f"Exposure: ${summary['total_exposure']:,.2f} ({summary['exposure_pct']:.1%})")
        lines.append(f"Cash: ${summary['cash']:,.2f} ({summary['cash_pct']:.1%})")
        lines.append(f"Positions: {summary['position_count']}/{summary['max_positions']}")
        lines.append("")

        if summary["positions"]:
            lines.append("Holdings:")
            for pos in summary["positions"]:
                pl_str = (
                    f"+${pos['unrealized_pl']:,.2f}"
                    if pos["unrealized_pl"] >= 0
                    else f"-${abs(pos['unrealized_pl']):,.2f}"
                )
                lines.append(
                    f"  {pos['symbol']:6} {pos['shares']:>6.0f} shares  "
                    f"${pos['market_value']:>10,.2f} ({pos['pct_of_portfolio']:>5.1%})  "
                    f"{pl_str}"
                )
        else:
            lines.append("  No positions")

        return "\n".join(lines)

    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of portfolio configuration."""
        return {
            "risk_per_trade_pct": f"{self.config.risk_per_trade_pct:.0%}",
            "max_position_pct": f"{self.config.max_position_pct:.0%}",
            "max_exposure_pct": f"{self.config.max_exposure_pct:.0%}",
            "max_open_positions": self.config.max_open_positions,
            "max_position_usd": f"${self.config.max_position_usd:,.0f}",
            "hard_block_on_limits": self.config.hard_block_on_limits,
        }


# Global instance
_portfolio_manager: Optional[PortfolioManager] = None


def get_portfolio_manager() -> PortfolioManager:
    """Get global portfolio manager instance."""
    global _portfolio_manager
    if _portfolio_manager is None:
        _portfolio_manager = PortfolioManager()
    return _portfolio_manager
