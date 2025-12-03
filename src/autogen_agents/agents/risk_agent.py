#!/usr/bin/env python3
"""
RiskAgent - Portfolio Risk Management and Position Sizing

Autonomous agent for pre-trade validation, position sizing, and portfolio risk limits.
Uses MACD+RSI voting signal confidence to scale position sizes appropriately.

Issue #387: RiskAgent - Portfolio Risk Management and Position Sizing

Key Responsibilities:
1. Position Sizing - Calculate based on account risk percentage and stop distance
2. Portfolio Risk Management - Track exposure, concentration, daily loss limits
3. Pre-Trade Validation - Check buying power, margin, position limits before execution
4. Circuit Breaker - Daily loss limit enforcement

Integration Points:
- Receives trade proposals from VoterAgent/Orchestrator
- Validates and sizes positions before ExecutorAgent execution
- Publishes RISK_VALIDATED or RISK_REJECTED events via AgentBus
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from config_defaults.trading_config import TradingConfig

from ..core.base_agent import BaseAgent
from src.trading_tools.risk_calculator import calculate_portfolio_risk, check_portfolio_limits
from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """Risk management configuration parameters."""

    # Position sizing
    max_position_pct: float = 0.10  # 10% max per position
    default_position_pct: float = 0.05  # 5% default per position
    max_portfolio_risk_per_trade: float = 0.02  # 2% portfolio risk per trade

    # Portfolio limits
    max_positions: int = 10  # Maximum concurrent positions
    max_portfolio_exposure: float = 0.80  # 80% max invested
    max_sector_exposure: float = 0.30  # 30% max per sector
    min_cash_reserve: float = 0.10  # Keep 10% cash minimum

    # Circuit breaker
    max_daily_loss_pct: float = 0.05  # 5% daily loss triggers circuit breaker
    circuit_breaker_cooldown_hours: int = 24

    # Validation thresholds
    min_risk_reward_ratio: float = 1.5  # Minimum R:R to approve
    warn_risk_reward_ratio: float = 2.0  # Warn if below this


@dataclass
class RiskValidationResult:
    """Result of risk validation for a proposed trade."""

    approved: bool
    reason: str

    # Position sizing
    recommended_quantity: int
    position_value: float
    portfolio_pct: float

    # Risk metrics
    max_loss_usd: float
    risk_reward_ratio: float

    # Warnings (trade can proceed but with caution)
    warnings: List[str]

    # Blocking issues (trade should not proceed)
    blocking_issues: List[str]

    # Account context
    buying_power: float
    portfolio_value: float
    current_exposure_pct: float

    # Metadata
    timestamp: str = ""
    symbol: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = now_iso()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "approved": self.approved,
            "reason": self.reason,
            "recommended_quantity": self.recommended_quantity,
            "position_value": self.position_value,
            "portfolio_pct": self.portfolio_pct,
            "max_loss_usd": self.max_loss_usd,
            "risk_reward_ratio": self.risk_reward_ratio,
            "warnings": self.warnings,
            "blocking_issues": self.blocking_issues,
            "buying_power": self.buying_power,
            "portfolio_value": self.portfolio_value,
            "current_exposure_pct": self.current_exposure_pct,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
        }


class RiskAgent(BaseAgent):
    """
    Autonomous risk management agent for trading system.

    Validates proposed trades, calculates position sizes, and enforces
    portfolio risk limits. Works with ExecutorAgent to ensure all trades
    meet risk parameters before execution.

    Key Features:
    - Risk-based position sizing using stop distance
    - Portfolio concentration limits
    - Daily loss circuit breaker
    - Pre-trade validation with clear approve/reject decisions
    - Configurable via TradingConfig
    """

    def __init__(
        self,
        name: str = "risk_agent",
        position_manager: Optional[Any] = None,
        risk_config: Optional[RiskConfig] = None,
        use_config_file: bool = True,
        **kwargs,
    ):
        """
        Initialize RiskAgent with optional position manager and config.

        Args:
            name: Agent identifier
            position_manager: PositionManager instance for account/position data
            risk_config: Override risk parameters
            use_config_file: Whether to load from TradingConfig
            **kwargs: Additional BaseAgent parameters
        """
        # Don't require LLM for pure risk calculations
        kwargs.setdefault("tools", [])
        super().__init__(name=name, **kwargs)

        self.position_manager = position_manager
        self._trading_config = TradingConfig() if use_config_file else None

        # Initialize risk configuration
        if risk_config:
            self.risk_config = risk_config
        elif use_config_file and self._trading_config:
            self.risk_config = self._load_risk_config_from_trading_config()
        else:
            self.risk_config = RiskConfig()

        # Track daily P&L for circuit breaker
        self._daily_pnl = 0.0
        self._daily_pnl_start_date: Optional[str] = None
        self._circuit_breaker_active = False

        # Track positions for concentration checks
        self._position_cache: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"RiskAgent '{name}' initialized with: "
            f"max_position={self.risk_config.max_position_pct:.0%}, "
            f"max_exposure={self.risk_config.max_portfolio_exposure:.0%}, "
            f"daily_loss_limit={self.risk_config.max_daily_loss_pct:.0%}"
        )

    def _load_risk_config_from_trading_config(self) -> RiskConfig:
        """Load risk parameters from TradingConfig if available."""
        try:
            risk_params = {}
            if hasattr(self._trading_config, "get_risk_param"):
                risk_params = {
                    "max_position_pct": self._trading_config.get_risk_param("max_position_pct")
                    or 0.10,
                    "max_portfolio_risk_per_trade": self._trading_config.get_risk_param(
                        "max_portfolio_risk_per_trade"
                    )
                    or 0.02,
                }

            return RiskConfig(**{k: v for k, v in risk_params.items() if v is not None})
        except Exception as e:
            logger.warning(f"Failed to load risk config from TradingConfig: {e}")
            return RiskConfig()

    def validate_trade(
        self,
        symbol: str,
        signal: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        confidence: float = 0.5,
        requested_quantity: Optional[int] = None,
    ) -> RiskValidationResult:
        """
        Validate a proposed trade and calculate position size.

        This is the core method called before any trade execution.

        Args:
            symbol: Ticker symbol
            signal: Trading signal ("BUY" or "SELL")
            entry_price: Proposed entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            confidence: Signal confidence from VoterAgent (0.0-1.0)
            requested_quantity: Optional user-requested quantity

        Returns:
            RiskValidationResult with approval decision and sizing
        """
        warnings = []
        blocking_issues = []

        # Get account info
        portfolio_value = self._get_portfolio_value()
        buying_power = self._get_buying_power()
        current_positions = self._get_current_positions()

        # Calculate current exposure
        total_position_value = sum(p.get("market_value", 0) for p in current_positions.values())
        current_exposure_pct = (
            (total_position_value / portfolio_value) if portfolio_value > 0 else 0
        )

        # Check circuit breaker
        if self._circuit_breaker_active:
            return RiskValidationResult(
                approved=False,
                reason="Circuit breaker active - daily loss limit exceeded",
                recommended_quantity=0,
                position_value=0,
                portfolio_pct=0,
                max_loss_usd=0,
                risk_reward_ratio=0,
                warnings=[],
                blocking_issues=["Circuit breaker active"],
                buying_power=buying_power,
                portfolio_value=portfolio_value,
                current_exposure_pct=current_exposure_pct,
                symbol=symbol,
            )

        # Check if we already have a position in this symbol
        existing_position = current_positions.get(symbol)
        if existing_position:
            existing_qty = existing_position.get("qty", 0)
            if existing_qty > 0 and signal == "BUY":
                warnings.append(f"Already holding {existing_qty} shares of {symbol}")
            elif existing_qty < 0 and signal == "SELL":
                warnings.append(f"Already short {abs(existing_qty)} shares of {symbol}")

        # Calculate position size
        if requested_quantity:
            quantity = requested_quantity
            sizing_method = "user_specified"
        else:
            quantity, sizing_method = self._calculate_position_size(
                portfolio_value=portfolio_value,
                entry_price=entry_price,
                stop_loss=stop_loss,
                confidence=confidence,
            )

        # Calculate trade metrics
        position_value = quantity * entry_price
        portfolio_pct = (position_value / portfolio_value) if portfolio_value > 0 else 0

        # Calculate risk metrics
        risk_per_share = abs(entry_price - stop_loss)
        max_loss_usd = risk_per_share * quantity

        # Calculate reward
        reward_per_share = abs(take_profit - entry_price)
        potential_gain = reward_per_share * quantity
        risk_reward_ratio = potential_gain / max_loss_usd if max_loss_usd > 0 else 0

        # Run validation checks
        self._check_buying_power(position_value, buying_power, warnings, blocking_issues)
        self._check_position_limits(portfolio_pct, warnings, blocking_issues)
        self._check_portfolio_exposure(
            current_exposure_pct, portfolio_pct, warnings, blocking_issues
        )
        self._check_max_positions(len(current_positions), warnings, blocking_issues)
        self._check_risk_reward(risk_reward_ratio, warnings, blocking_issues)

        # Determine approval
        approved = len(blocking_issues) == 0
        if approved:
            reason = f"Trade approved: {quantity} shares {symbol} at ${entry_price:.2f}"
        else:
            reason = f"Trade rejected: {'; '.join(blocking_issues)}"

        result = RiskValidationResult(
            approved=approved,
            reason=reason,
            recommended_quantity=quantity,
            position_value=position_value,
            portfolio_pct=portfolio_pct,
            max_loss_usd=max_loss_usd,
            risk_reward_ratio=risk_reward_ratio,
            warnings=warnings,
            blocking_issues=blocking_issues,
            buying_power=buying_power,
            portfolio_value=portfolio_value,
            current_exposure_pct=current_exposure_pct,
            symbol=symbol,
        )

        logger.info(
            f"Risk validation for {symbol}: approved={approved}, "
            f"qty={quantity}, R:R={risk_reward_ratio:.2f}, "
            f"method={sizing_method}"
        )

        return result

    def _calculate_position_size(
        self,
        portfolio_value: float,
        entry_price: float,
        stop_loss: float,
        confidence: float,
    ) -> tuple:
        """
        Calculate position size using risk-based sizing.

        Uses the risk per trade to determine shares based on stop distance.
        Scales by confidence level from VoterAgent.

        Returns:
            Tuple of (quantity, sizing_method)
        """
        # Method 1: Risk-based sizing (preferred)
        risk_per_share = abs(entry_price - stop_loss)

        if risk_per_share > 0:
            # Base risk amount (2% of portfolio)
            base_risk = portfolio_value * self.risk_config.max_portfolio_risk_per_trade

            # Scale by confidence (0.5-1.0 range typically)
            scaled_risk = base_risk * min(1.0, max(0.5, confidence))

            # Calculate shares
            quantity = int(scaled_risk / risk_per_share)

            # Check against max position size
            max_position_value = portfolio_value * self.risk_config.max_position_pct
            max_shares_by_value = int(max_position_value / entry_price)

            if quantity > max_shares_by_value:
                quantity = max_shares_by_value
                return (quantity, "risk_capped_by_position_limit")

            return (quantity, "risk_based")

        # Method 2: Fallback to percentage-based sizing
        target_value = portfolio_value * self.risk_config.default_position_pct
        quantity = int(target_value / entry_price)
        return (quantity, "percentage_based")

    def _check_buying_power(
        self,
        position_value: float,
        buying_power: float,
        warnings: List[str],
        blocking_issues: List[str],
    ):
        """Check if we have sufficient buying power."""
        if position_value > buying_power:
            blocking_issues.append(
                f"Insufficient buying power: need ${position_value:,.2f}, "
                f"have ${buying_power:,.2f}"
            )
        elif position_value > buying_power * 0.9:
            warnings.append(
                f"Trade uses {(position_value / buying_power) * 100:.0f}% of buying power"
            )

    def _check_position_limits(
        self,
        portfolio_pct: float,
        warnings: List[str],
        blocking_issues: List[str],
    ):
        """Check single position size limits."""
        if portfolio_pct > self.risk_config.max_position_pct:
            blocking_issues.append(
                f"Position too large: {portfolio_pct:.1%} > "
                f"{self.risk_config.max_position_pct:.0%} limit"
            )
        elif portfolio_pct > self.risk_config.max_position_pct * 0.8:
            warnings.append(f"Large position: {portfolio_pct:.1%} of portfolio")

    def _check_portfolio_exposure(
        self,
        current_exposure_pct: float,
        new_position_pct: float,
        warnings: List[str],
        blocking_issues: List[str],
    ):
        """Check total portfolio exposure after trade."""
        new_exposure = current_exposure_pct + new_position_pct

        if new_exposure > self.risk_config.max_portfolio_exposure:
            blocking_issues.append(
                f"Exceeds max exposure: {new_exposure:.1%} > "
                f"{self.risk_config.max_portfolio_exposure:.0%} limit"
            )
        elif new_exposure > self.risk_config.max_portfolio_exposure * 0.9:
            warnings.append(f"High portfolio exposure: {new_exposure:.1%}")

    def _check_max_positions(
        self,
        current_count: int,
        warnings: List[str],
        blocking_issues: List[str],
    ):
        """Check maximum number of positions."""
        if current_count >= self.risk_config.max_positions:
            blocking_issues.append(
                f"Max positions reached: {current_count}/{self.risk_config.max_positions}"
            )
        elif current_count >= self.risk_config.max_positions - 2:
            warnings.append(
                f"Near position limit: {current_count}/{self.risk_config.max_positions}"
            )

    def _check_risk_reward(
        self,
        risk_reward_ratio: float,
        warnings: List[str],
        blocking_issues: List[str],
    ):
        """Check risk/reward ratio."""
        if risk_reward_ratio < self.risk_config.min_risk_reward_ratio:
            blocking_issues.append(
                f"Poor R:R ratio: {risk_reward_ratio:.2f} < "
                f"{self.risk_config.min_risk_reward_ratio:.1f} minimum"
            )
        elif risk_reward_ratio < self.risk_config.warn_risk_reward_ratio:
            warnings.append(f"Low R:R ratio: {risk_reward_ratio:.2f}")

    def update_daily_pnl(self, pnl_change: float):
        """
        Update daily P&L and check circuit breaker.

        Should be called after each trade closes.

        Args:
            pnl_change: P&L change from closed trade
        """
        today = now_iso()[:10]  # Get date portion

        # Reset if new day
        if self._daily_pnl_start_date != today:
            self._daily_pnl = 0.0
            self._daily_pnl_start_date = today
            self._circuit_breaker_active = False

        self._daily_pnl += pnl_change

        # Check circuit breaker
        portfolio_value = self._get_portfolio_value()
        daily_loss_pct = abs(self._daily_pnl) / portfolio_value if portfolio_value > 0 else 0

        if self._daily_pnl < 0 and daily_loss_pct >= self.risk_config.max_daily_loss_pct:
            self._circuit_breaker_active = True
            logger.warning(
                f"CIRCUIT BREAKER ACTIVATED: Daily loss {daily_loss_pct:.1%} "
                f"exceeds {self.risk_config.max_daily_loss_pct:.0%} limit"
            )

    def get_portfolio_risk_summary(self) -> Dict[str, Any]:
        """
        Get current portfolio risk metrics.

        Returns:
            Dictionary with portfolio risk summary
        """
        portfolio_value = self._get_portfolio_value()
        buying_power = self._get_buying_power()
        positions = self._get_current_positions()

        # Calculate metrics using risk_calculator
        position_list = [
            {
                "symbol": symbol,
                "position_value": pos.get("market_value", 0),
                "unrealized_pnl": pos.get("unrealized_pl", 0),
            }
            for symbol, pos in positions.items()
        ]

        cash = buying_power
        risk_metrics = calculate_portfolio_risk(position_list, cash)

        # Check limits
        limits = check_portfolio_limits(
            current_positions=len(positions),
            position_exposure_pct=risk_metrics.position_exposure_pct,
            largest_position_pct=risk_metrics.largest_position_pct,
        )

        return {
            "portfolio_value": portfolio_value,
            "buying_power": buying_power,
            "position_count": len(positions),
            "exposure_pct": risk_metrics.position_exposure_pct,
            "largest_position_pct": risk_metrics.largest_position_pct,
            "total_unrealized_pnl": risk_metrics.total_unrealized_pnl,
            "daily_pnl": self._daily_pnl,
            "circuit_breaker_active": self._circuit_breaker_active,
            "limits_ok": limits["all_limits_ok"],
            "limit_details": limits,
            "timestamp": now_iso(),
        }

    def _get_portfolio_value(self) -> float:
        """Get portfolio value from position manager or fallback."""
        if self.position_manager:
            try:
                account = self.position_manager.get_account_info()
                return float(account.get("portfolio_value", 100000))
            except Exception as e:
                logger.warning(f"Failed to get portfolio value: {e}")

        # Fallback for testing
        return 100000.0

    def _get_buying_power(self) -> float:
        """Get buying power from position manager or fallback."""
        if self.position_manager:
            try:
                account = self.position_manager.get_account_info()
                return float(account.get("buying_power", 50000))
            except Exception as e:
                logger.warning(f"Failed to get buying power: {e}")

        # Fallback for testing
        return 50000.0

    def _get_current_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get current positions from position manager."""
        if self.position_manager:
            try:
                return self.position_manager.get_positions()
            except Exception as e:
                logger.warning(f"Failed to get positions: {e}")

        return self._position_cache

    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's required method for handling incoming messages.

        Expected message format for trade validation:
        {
            "command": "validate_trade",
            "symbol": "AAPL",
            "signal": "BUY",
            "entry_price": 150.0,
            "stop_loss": 145.0,
            "take_profit": 165.0,
            "confidence": 0.75
        }

        Or for portfolio summary:
        {
            "command": "portfolio_summary"
        }
        """
        if not messages:
            return json.dumps({"error": "No messages to process"})

        # Get the latest message
        latest_message = messages[-1]
        if hasattr(latest_message, "content"):
            content = latest_message.content
        else:
            content = str(latest_message)

        try:
            if isinstance(content, str):
                command_data = json.loads(content)
            else:
                command_data = content

            command = command_data.get("command", "validate_trade")

            if command == "validate_trade":
                result = self.validate_trade(
                    symbol=command_data.get("symbol", "UNKNOWN"),
                    signal=command_data.get("signal", "BUY"),
                    entry_price=command_data.get("entry_price", 0),
                    stop_loss=command_data.get("stop_loss", 0),
                    take_profit=command_data.get("take_profit", 0),
                    confidence=command_data.get("confidence", 0.5),
                    requested_quantity=command_data.get("quantity"),
                )
                return json.dumps(result.to_dict(), indent=2)

            elif command == "portfolio_summary":
                summary = self.get_portfolio_risk_summary()
                return json.dumps(summary, indent=2)

            elif command == "update_pnl":
                pnl_change = command_data.get("pnl_change", 0)
                self.update_daily_pnl(pnl_change)
                return json.dumps(
                    {
                        "status": "updated",
                        "daily_pnl": self._daily_pnl,
                        "circuit_breaker_active": self._circuit_breaker_active,
                    }
                )

            else:
                return json.dumps({"error": f"Unknown command: {command}"})

        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON in message"})
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return json.dumps({"error": str(e)})

    def get_current_configuration(self) -> Dict[str, Any]:
        """Return current risk configuration."""
        return {
            "max_position_pct": self.risk_config.max_position_pct,
            "default_position_pct": self.risk_config.default_position_pct,
            "max_portfolio_risk_per_trade": self.risk_config.max_portfolio_risk_per_trade,
            "max_positions": self.risk_config.max_positions,
            "max_portfolio_exposure": self.risk_config.max_portfolio_exposure,
            "max_daily_loss_pct": self.risk_config.max_daily_loss_pct,
            "min_risk_reward_ratio": self.risk_config.min_risk_reward_ratio,
        }


def create_risk_agent(
    name: str = "risk_agent",
    position_manager: Optional[Any] = None,
    **kwargs,
) -> RiskAgent:
    """Factory function to create a properly configured risk agent."""
    return RiskAgent(name=name, position_manager=position_manager, **kwargs)
