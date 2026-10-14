"""
SimpleRiskManager - Basic portfolio % and buying power checks.

MVP implementation for #308. Upgrade to full Portfolio Manager (#333) later.
"""

import logging
from typing import Dict, List, Optional, Tuple

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
    - Generate warnings
    - Block trades that open or add to a position beyond buying power, max exposure
      or max positions (selling shares already held isn't subject to these limits)

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
        1. Get open positions, portfolio value and buying power
        2. If user specified quantity, use it; otherwise calculate from % (a sell of
           a held position defaults to the whole position)
        3. Check if affordable (buying power check)
        4. Calculate portfolio % and projected exposure from open positions
        5. Generate warnings (>15% = large position)
        6. Block (approved=False, with block_reasons) when a trade that opens or adds
           to a position breaks buying power, max exposure or max positions, or when
           account data can't be read. Selling shares already held only reduces risk:
           account limits don't apply and it only needs the positions, but selling
           more than is held (a short) is blocked.

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
            held = {
                p["symbol"]: p
                for p in await self.get_positions(user_id)
                if float(p.get("qty") or 0) != 0
            }
            existing_qty = float(held[ticker]["qty"]) if ticker in held else 0.0
            # Selling shares already held only reduces risk, so account limits don't apply
            is_exit = analysis.signal.value == "sell" and existing_qty > 0

            if is_exit:
                # Without a quantity, a sell closes the whole position
                quantity = request.quantity or int(existing_qty)
                portfolio_value, buying_power = await self._exit_account_values(user_id)
            else:
                portfolio_value = await self.get_portfolio_value(user_id)
                buying_power = await self.get_buying_power(user_id, portfolio_value=portfolio_value)
                if portfolio_value <= 0:
                    raise ValueError("the account has no portfolio value to size a trade against")
                quantity = self._quantity(request, portfolio_value, entry_price)

            # Calculate trade value
            trade_value = quantity * entry_price

            # Calculate portfolio % (after transaction)
            portfolio_pct = (trade_value / portfolio_value) * 100.0 if portfolio_value > 0 else 0.0

            if is_exit:
                warnings, block_reasons = [], []
                if quantity > existing_qty:
                    block_reasons.append(
                        f"Can't sell {quantity} shares of {ticker}: only {existing_qty:g} held "
                        "(short selling isn't supported)"
                    )
            else:
                warnings, block_reasons = self._limit_breaches(
                    ticker, trade_value, buying_power, portfolio_value, portfolio_pct, held
                )

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

            # Block trade if critical limits are violated
            for reason in block_reasons:
                logger.warning(f"Trade blocked for {ticker}: {reason}")
            # Note: Other warnings (large position, diversification) don't block trades

            # Create assessment
            assessment = RiskAssessment(
                approved=not block_reasons,
                recommended_quantity=quantity,
                portfolio_pct=portfolio_pct,
                max_loss_usd=max_loss_usd,
                risk_reward_ratio=risk_reward_ratio,
                warnings=warnings,
                buying_power_available=buying_power,
                existing_position_qty=int(existing_qty),
                block_reasons=block_reasons,
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
                block_reasons=[f"Risk assessment error: {e}"],
            )

    def _quantity(self, request: TradeRequest, portfolio_value: float, entry_price: float) -> int:
        """Shares for a new position: the user's quantity, else the default portfolio %."""
        if request.quantity:
            # User specified quantity - use it
            logger.info(f"Using user-specified quantity: {request.quantity} shares")
            return request.quantity

        # Calculate from default portfolio %
        target_value = portfolio_value * (self.default_position_pct / 100.0)
        quantity = int(target_value / entry_price)
        logger.info(
            f"Calculated quantity: {quantity} shares "
            f"({self.default_position_pct}% of ${portfolio_value:,.0f})"
        )
        return quantity

    async def _exit_account_values(self, user_id: str) -> Tuple[float, float]:
        """
        Portfolio value and buying power to show for an exit, or 0.0 if unreadable.

        An exit doesn't depend on them, so a failed read doesn't block it.
        """
        try:
            portfolio_value = await self.get_portfolio_value(user_id)
            buying_power = await self.get_buying_power(user_id, portfolio_value=portfolio_value)
            return portfolio_value, buying_power
        except Exception as e:
            logger.warning(f"Could not read account values for an exit: {e}")
            return 0.0, 0.0

    def _limit_breaches(
        self,
        ticker: str,
        trade_value: float,
        buying_power: float,
        portfolio_value: float,
        portfolio_pct: float,
        held: Dict[str, dict],
    ) -> Tuple[List[str], List[str]]:
        """Warnings and blocking reasons for a trade that opens or adds to a position."""
        warnings: List[str] = []
        block_reasons: List[str] = []

        # Check buying power
        if trade_value > buying_power:
            reason = (
                f"Insufficient buying power: need ${trade_value:,.2f}, "
                f"have ${buying_power:,.2f}"
            )
            warnings.append(f"⚠️  {reason}")
            block_reasons.append(reason)

        # Warning for large positions
        if portfolio_pct > self.max_position_pct:
            warnings.append(
                f"⚠️  Large position: {portfolio_pct:.1f}% of portfolio "
                f"(>{self.max_position_pct}% threshold)"
            )

        # Portfolio-level limits after this trade, from the open positions
        position_pcts = {
            symbol: abs(float(p.get("market_value") or 0)) / portfolio_value * 100.0
            for symbol, p in held.items()
        }
        projected_exposure_pct = sum(position_pcts.values()) + portfolio_pct
        projected_positions_count = len(held) + (0 if ticker in held else 1)
        position_pcts[ticker] = position_pcts.get(ticker, 0.0) + portfolio_pct

        limits_config = {
            "max_positions": self.config.get("risk.max_positions", 10),
            "max_exposure_pct": self.config.get("risk.max_exposure_pct", 80.0),
            "max_single_position_pct": self.max_position_pct,
        }

        limits_check = check_portfolio_limits(
            current_positions=projected_positions_count,
            position_exposure_pct=projected_exposure_pct,
            largest_position_pct=max(position_pcts.values()),
            limits_config=limits_config,
        )

        if not limits_check.get("max_positions", True):
            reason = (
                f"Portfolio limit: Would exceed max positions "
                f"({projected_positions_count} > {limits_config['max_positions']})"
            )
            warnings.append(f"⚠️  {reason}")
            block_reasons.append(reason)

        if not limits_check.get("max_exposure", True):
            reason = (
                f"Portfolio limit: Would exceed max exposure "
                f"({projected_exposure_pct:.1f}% > {limits_config['max_exposure_pct']}%)"
            )
            warnings.append(f"⚠️  {reason}")
            block_reasons.append(reason)

        if not limits_check.get("diversification_ok", True):
            warnings.append("⚠️  Diversification warning: Position concentration too high")

        return warnings, block_reasons

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
            # Errors propagate: demo values would approve trades against a fake account
            return await self.account.get_portfolio_value(user_id)

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
            # Errors propagate: demo values would approve trades against a fake account
            return await self.account.get_buying_power(user_id)

        # MVP: Using demo buying power (account service not configured)
        # This is expected during MVP - only log at DEBUG level
        if portfolio_value is None:
            portfolio_value = await self.get_portfolio_value(user_id)
        buying_power = portfolio_value * 0.5
        logger.debug(
            f"Account service not configured - using demo buying power: ${buying_power:,.0f}"
        )
        return buying_power

    async def get_positions(self, user_id: str = "default") -> List[dict]:
        """
        Get open positions for user.

        MVP: If account service not available (or has no positions lookup), return [].

        Args:
            user_id: User ID

        Returns:
            Position dicts with symbol, qty and market_value
        """
        if self.account and hasattr(self.account, "get_positions"):
            return await self.account.get_positions(user_id)
        return []
