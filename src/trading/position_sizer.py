#!/usr/bin/env python3
"""
Position Sizer - Profile-Based Position Sizing Automation

Issue #416: Position Sizing Automation - Profile-Based Allocation

Automates position sizing based on:
- Trading mode profiles (conservative/moderate/aggressive)
- Per-ticker limits from ApprovedTickersManager (#415)
- Buying power constraints
- Existing position awareness

Phases:
- Phase 1: Profile-based sizing ✓
- Phase 2: Risk-based sizing (calculate shares from risk amount + stop distance)
- Phase 3: Smart sizing (correlation check, volatility adjustment)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.core.trading_modes import TradingMode, TradingModeManager, get_mode_manager
from src.trading.approved_tickers import ApprovedTickersManager
from src.trading.ticker_database import TickerMode

logger = logging.getLogger(__name__)


class SizingMode(Enum):
    """Position sizing calculation mode."""

    PROFILE_BASED = "profile_based"  # Use trading mode profile
    FIXED_DOLLAR = "fixed_dollar"  # Fixed dollar amount
    FIXED_SHARES = "fixed_shares"  # Fixed number of shares
    RISK_BASED = "risk_based"  # Based on risk amount and stop distance (Phase 2)


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""

    symbol: str
    shares: int
    position_value: float
    price_per_share: float

    # Context
    trading_mode: TradingMode
    sizing_mode: SizingMode

    # Limits applied
    max_position_pct: float
    max_position_value: float
    ticker_limit: Optional[float]  # Per-ticker override from #415

    # Validation
    buying_power_available: float
    is_valid: bool
    validation_message: str

    # Risk info
    stop_price: Optional[float] = None
    risk_per_share: Optional[float] = None
    total_risk: Optional[float] = None

    def __str__(self) -> str:
        """Human-readable summary."""
        if not self.is_valid:
            return f"{self.symbol}: {self.validation_message}"

        mode_str = self.trading_mode.value.capitalize()
        return (
            f"{self.symbol}: {self.shares} shares @ ${self.price_per_share:.2f} "
            f"(${self.position_value:,.2f}) [{mode_str}]"
        )


class PositionSizer:
    """
    Automated position sizing based on trading profiles.

    Issue #416: Position Sizing Automation

    Calculates optimal position sizes considering:
    - Trading mode parameters (max position %)
    - Per-ticker limits from approved tickers list
    - Available buying power
    - Existing positions
    """

    def __init__(
        self,
        mode_manager: Optional[TradingModeManager] = None,
        tickers_manager: Optional[ApprovedTickersManager] = None,
    ):
        """
        Initialize position sizer.

        Args:
            mode_manager: Trading mode manager (default: global instance)
            tickers_manager: Approved tickers manager (optional)
        """
        self.mode_manager = mode_manager or get_mode_manager()
        self.tickers_manager = tickers_manager

        # Default sizing mode
        self.default_sizing_mode = SizingMode.PROFILE_BASED

        # Fixed amount settings (for FIXED_DOLLAR/FIXED_SHARES modes)
        self.fixed_dollar_amount: float = 5000.0
        self.fixed_shares_count: int = 100

        logger.info("PositionSizer initialized")

    def calculate_position_size(
        self,
        symbol: str,
        current_price: float,
        portfolio_value: float,
        buying_power: float,
        existing_position_value: float = 0.0,
        mode: Optional[TradingMode] = None,
        sizing_mode: Optional[SizingMode] = None,
        stop_price: Optional[float] = None,
    ) -> PositionSizeResult:
        """
        Calculate recommended position size for a symbol.

        Args:
            symbol: Ticker symbol
            current_price: Current market price per share
            portfolio_value: Total portfolio value
            buying_power: Available buying power
            existing_position_value: Value of existing position in this symbol
            mode: Trading mode override (default: current mode)
            sizing_mode: Sizing calculation mode (default: PROFILE_BASED)
            stop_price: Stop loss price (for risk calculation)

        Returns:
            PositionSizeResult with calculated size and validation
        """
        mode = mode or self.mode_manager.current_mode
        sizing_mode = sizing_mode or self.default_sizing_mode

        # Get mode parameters
        params = self.mode_manager.get_parameters(mode)

        # Calculate limits
        max_pct = params.max_position_pct
        max_value = params.max_position_value
        portfolio_limit = portfolio_value * max_pct

        # Use lower of percentage-based and absolute limit
        mode_limit = min(portfolio_limit, max_value)

        # Check for per-ticker override from #415
        ticker_limit = None
        if self.tickers_manager:
            ticker_config = self.tickers_manager.get_ticker(symbol)
            if ticker_config and ticker_config.max_position:
                ticker_limit = ticker_config.max_position
                mode_limit = min(mode_limit, ticker_limit)

        # Account for existing position
        available_for_position = mode_limit - existing_position_value

        # Apply sizing mode
        if sizing_mode == SizingMode.FIXED_DOLLAR:
            target_value = self.fixed_dollar_amount
        elif sizing_mode == SizingMode.FIXED_SHARES:
            target_value = self.fixed_shares_count * current_price
        else:  # PROFILE_BASED
            target_value = available_for_position

        # Constrain to what's available
        target_value = min(target_value, available_for_position, buying_power)

        # Calculate shares
        if current_price > 0:
            shares = int(target_value / current_price)
        else:
            shares = 0

        # Final position value
        position_value = shares * current_price

        # Validate
        is_valid, validation_msg = self._validate_size(
            symbol=symbol,
            shares=shares,
            position_value=position_value,
            buying_power=buying_power,
            current_price=current_price,
        )

        # Calculate risk if stop provided
        risk_per_share = None
        total_risk = None
        if stop_price and stop_price < current_price:
            risk_per_share = current_price - stop_price
            total_risk = risk_per_share * shares

        return PositionSizeResult(
            symbol=symbol,
            shares=shares,
            position_value=position_value,
            price_per_share=current_price,
            trading_mode=mode,
            sizing_mode=sizing_mode,
            max_position_pct=max_pct,
            max_position_value=max_value,
            ticker_limit=ticker_limit,
            buying_power_available=buying_power,
            is_valid=is_valid,
            validation_message=validation_msg,
            stop_price=stop_price,
            risk_per_share=risk_per_share,
            total_risk=total_risk,
        )

    def _validate_size(
        self,
        symbol: str,
        shares: int,
        position_value: float,
        buying_power: float,
        current_price: float,
    ) -> tuple[bool, str]:
        """
        Validate the calculated position size.

        Returns:
            Tuple of (is_valid, message)
        """
        # Check if ticker is approved for trading
        if self.tickers_manager:
            ticker = self.tickers_manager.get_ticker(symbol)
            if ticker:
                if ticker.mode == TickerMode.DISABLED:
                    return False, f"{symbol} is disabled for trading"
                if ticker.mode == TickerMode.WATCH_ONLY:
                    return False, f"{symbol} is watch-only (no trading allowed)"

        # Check shares
        if shares <= 0:
            if buying_power < current_price:
                return (
                    False,
                    f"Insufficient buying power (${buying_power:.2f} < ${current_price:.2f})",
                )
            return False, "Position size too small"

        # Check buying power
        if position_value > buying_power:
            return False, f"Exceeds buying power (${position_value:.2f} > ${buying_power:.2f})"

        # Valid
        return True, f"OK: {shares} shares @ ${current_price:.2f}"

    def get_suggested_size_summary(
        self,
        symbol: str,
        current_price: float,
        portfolio_value: float,
        buying_power: float,
        existing_position_value: float = 0.0,
        mode: Optional[TradingMode] = None,
        stop_price: Optional[float] = None,
    ) -> str:
        """
        Get human-readable position sizing summary.

        Args:
            symbol: Ticker symbol
            current_price: Current price
            portfolio_value: Total portfolio value
            buying_power: Available buying power
            existing_position_value: Existing position value
            mode: Trading mode override
            stop_price: Stop loss price

        Returns:
            Formatted summary string
        """
        result = self.calculate_position_size(
            symbol=symbol,
            current_price=current_price,
            portfolio_value=portfolio_value,
            buying_power=buying_power,
            existing_position_value=existing_position_value,
            mode=mode,
            stop_price=stop_price,
        )

        mode_name = result.trading_mode.value.capitalize()

        lines = [
            f"Position Sizing ({mode_name} mode):",
            f"  Max position: {result.max_position_pct:.0%} of ${portfolio_value:,.0f} = ${portfolio_value * result.max_position_pct:,.0f}",
        ]

        if result.ticker_limit:
            lines.append(f"  Ticker limit: ${result.ticker_limit:,.0f} (per-ticker override)")

        if existing_position_value > 0:
            lines.append(f"  Existing position: ${existing_position_value:,.2f}")

        lines.append(f"  Buying power: ${buying_power:,.2f}")
        lines.append("")

        if result.is_valid:
            lines.append(f"  Suggested: {result.shares} shares @ ${current_price:.2f}")
            lines.append(f"  Position value: ${result.position_value:,.2f}")

            if result.stop_price and result.total_risk:
                stop_pct = (current_price - result.stop_price) / current_price
                lines.append(f"  Stop @ ${result.stop_price:.2f} ({stop_pct:.1%})")
                lines.append(f"  Risk: ${result.total_risk:,.2f}")
        else:
            lines.append(f"  ⚠ {result.validation_message}")

        return "\n".join(lines)

    def can_open_position(
        self,
        symbol: str,
        current_price: float,
        buying_power: float,
    ) -> bool:
        """
        Quick check if a position can be opened for this symbol.

        Args:
            symbol: Ticker symbol
            current_price: Current price
            buying_power: Available buying power

        Returns:
            True if at least 1 share can be purchased
        """
        # Check approved list first
        if self.tickers_manager:
            if not self.tickers_manager.can_open_position(symbol):
                return False

        # Check buying power
        return buying_power >= current_price

    def calculate_shares_from_risk(
        self,
        risk_amount: float,
        current_price: float,
        stop_price: float,
        buying_power: float,
    ) -> tuple[int, float]:
        """
        Calculate shares based on fixed risk amount (Phase 2 preview).

        Args:
            risk_amount: Maximum amount willing to risk
            current_price: Current price per share
            stop_price: Stop loss price
            buying_power: Available buying power

        Returns:
            Tuple of (shares, position_value)
        """
        if stop_price >= current_price:
            logger.warning("Stop price must be below current price")
            return 0, 0.0

        risk_per_share = current_price - stop_price
        shares = int(risk_amount / risk_per_share)

        position_value = shares * current_price

        # Constrain to buying power
        if position_value > buying_power:
            shares = int(buying_power / current_price)
            position_value = shares * current_price

        return shares, position_value


# Global instance for easy access
_position_sizer: Optional[PositionSizer] = None


def get_position_sizer() -> PositionSizer:
    """Get global position sizer instance."""
    global _position_sizer
    if _position_sizer is None:
        _position_sizer = PositionSizer()
    return _position_sizer


def calculate_position_size(
    symbol: str,
    current_price: float,
    portfolio_value: float,
    buying_power: float,
    existing_position_value: float = 0.0,
    mode: Optional[TradingMode] = None,
) -> PositionSizeResult:
    """Convenience function for position sizing."""
    return get_position_sizer().calculate_position_size(
        symbol=symbol,
        current_price=current_price,
        portfolio_value=portfolio_value,
        buying_power=buying_power,
        existing_position_value=existing_position_value,
        mode=mode,
    )
