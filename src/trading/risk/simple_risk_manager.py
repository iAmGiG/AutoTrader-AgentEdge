"""
SimpleRiskManager - Basic portfolio % and buying power checks.

MVP implementation for #308. Upgrade to full Portfolio Manager (#333) later.
"""

import logging
from typing import Optional

from core.interfaces import RiskManager
from core.models import AnalysisResult, RiskAssessment, TradeRequest

from src.trading.risk.risk_calculator import check_portfolio_limits
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class SimpleRiskManager(RiskManager):
    """
    Simple risk management for MVP.

    Responsibilities:
    - Check buying power (can afford the trade?)
    - Calculate portfolio % allocation
    - Simple position sizing (default 5% of portfolio)
    - Generate warnings (but don't block trades)

    NOT included (deferred to #333 Portfolio Manager):
    - Sector concentration limits
    - Correlation analysis
    - Existing position conflict detection
    - Advanced position sizing (risk-based, volatility-adjusted)
    """

    def __init__(
        self,
        account_service: Optional[object] = None,  # AccountService (to be injected)
        default_position_pct: float = 5.0,  # Default: 5% of portfolio per position
        max_position_pct: float = 15.0,  # Warning threshold
    ):
        """
        Initialize SimpleRiskManager.

        Args:
            account_service: Service to query account info (portfolio value, buying power)
            default_position_pct: Default position size as % of portfolio (default: 5%)
            max_position_pct: Warning threshold for large positions (default: 15%)
        """
        self.account = account_service
        self.config = ConfigLoader()

        self.default_position_pct = self.config.get(
            "risk.default_position_pct", default_position_pct
        )
        self.max_position_pct = self.config.get("risk.max_position_pct", max_position_pct)

        logger.info(
            f"SimpleRiskManager initialized: "
            f"default_position={default_position_pct}%, "
            f"max_warning={max_position_pct}%"
        )

    async def assess(  # noqa: C901
        self, request: TradeRequest, analysis: AnalysisResult, user_id: str = "default"
    ) -> RiskAssessment:
        """
        Assess risk and recommend position size.

        MVP Logic:
        1. Get portfolio value and buying power
        2. If user specified quantity, use it; otherwise calculate from %
        3. Check if affordable (buying power check)
        4. Calculate portfolio %
        5. Generate warnings (>15% = large position)
        6. Always approve (warnings only, no blocking)

        Args:
            request: Original trade request
            analysis: Strategy analysis result
            user_id: User ID for portfolio lookup

        Returns:
            RiskAssessment with warnings and position sizing
        """
        ticker = request.ticker
        entry_price = analysis.entry_price
        stop_loss = analysis.stop_loss

        # Handle HOLD signals or fallback results (no entry price)
        if entry_price is None:
            logger.info(f"No entry price for {ticker} - signal is HOLD or analysis failed")
            return RiskAssessment(
                approved=False,
                recommended_quantity=0,
                portfolio_pct=0.0,
                max_loss_usd=0.0,
                risk_reward_ratio=0.0,
                warnings=[f"No entry price available for {ticker} - HOLD signal"],
                buying_power_available=0.0,
                existing_position_qty=0,
            )

        try:
            # Get portfolio info
            portfolio_value = await self.get_portfolio_value(user_id)
            buying_power = await self.get_buying_power(user_id, portfolio_value=portfolio_value)

            # Determine quantity
            if request.quantity:
                # User specified quantity - use it
                quantity = request.quantity
                logger.info(f"Using user-specified quantity: {quantity} shares")
            else:
                # Calculate from default portfolio %
                target_value = portfolio_value * (self.default_position_pct / 100.0)
                quantity = int(target_value / entry_price)
                logger.info(
                    f"Calculated quantity: {quantity} shares "
                    f"({self.default_position_pct}% of ${portfolio_value:,.0f})"
                )

            # Calculate trade value
            trade_value = quantity * entry_price

            # Check buying power
            warnings = []
            if trade_value > buying_power:
                warnings.append(
                    f"⚠️  Insufficient buying power: need ${trade_value:,.2f}, "
                    f"have ${buying_power:,.2f}"
                )

            # Calculate portfolio % (after transaction)
            portfolio_pct = (trade_value / portfolio_value) * 100.0

            # Warning for large positions
            if portfolio_pct > self.max_position_pct:
                warnings.append(
                    f"⚠️  Large position: {portfolio_pct:.1f}% of portfolio "
                    f"(>{self.max_position_pct}% threshold)"
                )

            # Portfolio-level risk checks
            # Get current positions count and exposure (simplified for MVP)
            # TODO: Integrate with actual PositionManager when available
            current_positions_count = 0  # Placeholder - would get from PositionManager
            current_exposure_pct = 0.0  # Placeholder - would calculate from positions

            # After this trade, what would exposure be?
            projected_exposure_pct = current_exposure_pct + portfolio_pct
            projected_positions_count = current_positions_count + 1

            # Check portfolio limits
            limits_config = {
                "max_positions": self.config.get("risk.max_positions", 10),
                "max_exposure_pct": self.config.get("risk.max_exposure_pct", 80.0),
                "max_single_position_pct": self.max_position_pct,
            }

            limits_check = check_portfolio_limits(
                current_positions=projected_positions_count,
                position_exposure_pct=projected_exposure_pct,
                largest_position_pct=max(portfolio_pct, current_exposure_pct),
                limits_config=limits_config,
            )

            # Add warnings for limit violations
            if not limits_check.get("max_positions", True):
                warnings.append(
                    f"⚠️  Portfolio limit: Would exceed max positions "
                    f"({projected_positions_count} > {limits_config['max_positions']})"
                )

            if not limits_check.get("max_exposure", True):
                warnings.append(
                    f"⚠️  Portfolio limit: Would exceed max exposure "
                    f"({projected_exposure_pct:.1f}% > {limits_config['max_exposure_pct']}%)"
                )

            if not limits_check.get("diversification_ok", True):
                warnings.append("⚠️  Diversification warning: Position concentration too high")

            # Calculate risk metrics (with None guards for stop_loss/take_profit)
            if stop_loss is not None:
                risk_per_share = abs(entry_price - stop_loss)
                max_loss_usd = risk_per_share * quantity
            else:
                # No stop loss defined - estimate 2% risk
                risk_per_share = entry_price * 0.02
                max_loss_usd = risk_per_share * quantity
                warnings.append("⚠️  No stop loss defined - using 2% estimate")

            # Calculate risk/reward ratio
            if analysis.take_profit is not None:
                if analysis.signal.value == "buy":
                    potential_gain = abs(analysis.take_profit - entry_price) * quantity
                elif analysis.signal.value == "sell":
                    potential_gain = abs(entry_price - analysis.take_profit) * quantity
                else:
                    potential_gain = 0
            else:
                potential_gain = 0

            risk_reward_ratio = potential_gain / max_loss_usd if max_loss_usd > 0 else 0.0

            # Determine approval based on portfolio limits and buying power
            # Block trade if critical limits are violated
            approved = True
            if trade_value > buying_power:
                approved = False
                logger.warning(f"Trade blocked: insufficient buying power for {ticker}")
            elif not limits_check.get("max_exposure", True):
                approved = False
                logger.warning(f"Trade blocked: would exceed max exposure limit for {ticker}")
            elif not limits_check.get("max_positions", True):
                approved = False
                logger.warning(f"Trade blocked: would exceed max positions limit for {ticker}")
            # Note: Other warnings (large position, diversification) don't block trades

            # Create assessment
            assessment = RiskAssessment(
                approved=approved,
                recommended_quantity=quantity,
                portfolio_pct=portfolio_pct,
                max_loss_usd=max_loss_usd,
                risk_reward_ratio=risk_reward_ratio,
                warnings=warnings,
                buying_power_available=buying_power,
                existing_position_qty=0,  # MVP: Not checking existing positions yet
            )

            logger.info(
                f"Risk assessment: {quantity} shares {ticker} = "
                f"{portfolio_pct:.1f}% portfolio, "
                f"max loss ${max_loss_usd:.2f}, "
                f"R/R {risk_reward_ratio:.2f}"
            )

            return assessment

        except Exception as e:
            logger.error(f"Risk assessment error: {e}", exc_info=True)
            # FAIL-SAFE: Block trade on error
            return RiskAssessment(
                approved=False,
                recommended_quantity=0,
                portfolio_pct=0.0,
                max_loss_usd=0.0,
                risk_reward_ratio=0.0,
                warnings=[f"⚠️  Risk assessment error: {e}"],
            )

    async def get_portfolio_value(self, user_id: str = "default") -> float:
        """
        Get total portfolio value for user.

        MVP: If account service not available, return placeholder.

        Args:
            user_id: User ID

        Returns:
            Total portfolio value in USD
        """
        if self.account:
            try:
                return await self.account.get_portfolio_value(user_id)
            except Exception as e:
                # Real error - log at warning level
                logger.warning(f"Failed to get portfolio value: {e}")
                # Fall through to use demo values

        # MVP: Using demo portfolio value (account service not configured)
        # This is expected during MVP - only log at DEBUG level
        logger.debug("Account service not configured - using demo portfolio: $100,000")
        return 100000.0

    async def get_buying_power(
        self, user_id: str = "default", portfolio_value: Optional[float] = None
    ) -> float:
        """
        Get available buying power for user.

        MVP: If account service not available, return placeholder.

        Args:
            user_id: User ID
            portfolio_value: Optional pre-calculated portfolio value to avoid duplicate logging

        Returns:
            Available cash in USD
        """
        if self.account:
            try:
                return await self.account.get_buying_power(user_id)
            except Exception as e:
                # Real error - log at warning level
                logger.warning(f"Failed to get buying power: {e}")
                # Fall through to use demo values

        # MVP: Using demo buying power (account service not configured)
        # This is expected during MVP - only log at DEBUG level
        if portfolio_value is None:
            portfolio_value = await self.get_portfolio_value(user_id)
        buying_power = portfolio_value * 0.5
        logger.debug(
            f"Account service not configured - using demo buying power: ${buying_power:,.0f}"
        )
        return buying_power
