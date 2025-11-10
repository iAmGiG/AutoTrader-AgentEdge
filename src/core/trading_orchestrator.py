"""
TradingOrchestrator - Central coordinator for the trading system.

This is the main business logic layer that all presentation layers (CLI, GUI, API) use.
It coordinates the workflow: parse → analyze → risk check → suggest → execute.
"""

import logging
from typing import Optional
from datetime import datetime
import uuid

from .models import (
    TradeRequest,
    AnalysisResult,
    RiskAssessment,
    TradeSuggestion,
    TradeDecision,
    OrderResult,
    Signal,
    TimeInForce,
    OrderType,
)
from .interfaces import (
    InputParser,
    StrategyAnalyzer,
    RiskManager,
    ExecutionManager,
)


logger = logging.getLogger(__name__)


class TradingOrchestrator:
    """
    Central coordinator for all trading operations.

    All UIs (CLI, GUI, Web API) use this orchestrator to process trades.
    This ensures consistent business logic regardless of presentation layer.

    Architecture:
        User Input → InputParser → StrategyAnalyzer → RiskManager → User Confirmation → ExecutionManager

    The orchestrator:
    1. Parses user input into TradeRequest
    2. Routes to appropriate strategy analyzer
    3. Assesses risk and position sizing
    4. Creates suggestion for user
    5. Executes trade on confirmation
    6. Tracks session state
    """

    def __init__(
        self,
        input_parser: InputParser,
        strategy_analyzer: StrategyAnalyzer,
        risk_manager: RiskManager,
        execution_manager: ExecutionManager,
        session_store: Optional[object] = None,  # SessionStore interface (to be created)
    ):
        """
        Initialize the orchestrator with pluggable components.

        Args:
            input_parser: Component to parse user input
            strategy_analyzer: Component to analyze trades
            risk_manager: Component to assess risk
            execution_manager: Component to execute orders
            session_store: Optional session persistence (SQLite)
        """
        self.parser = input_parser
        self.analyzer = strategy_analyzer
        self.risk = risk_manager
        self.executor = execution_manager
        self.session_store = session_store

        logger.info(
            f"TradingOrchestrator initialized with "
            f"analyzer={strategy_analyzer.name}, "
            f"parser={type(input_parser).__name__}"
        )

    async def process_request(
        self,
        user_input: str,
        user_id: str = "default"
    ) -> TradeDecision:
        """
        Main workflow: Process user request and generate trade suggestion.

        This is the primary entry point for all UIs.

        Args:
            user_input: Raw user input (e.g., "is SPY at 600 good?")
            user_id: User ID for portfolio lookups

        Returns:
            TradeDecision with suggestion (awaiting user confirmation)

        Raises:
            ValueError: If input cannot be parsed or analyzed
        """
        logger.info(f"Processing request from user {user_id}: {user_input}")

        try:
            # Step 1: Parse input
            request = await self.parser.parse(user_input, user_id)
            logger.debug(f"Parsed request: {request}")

            # Step 2: Validate request
            is_valid = await self.parser.validate(request)
            if not is_valid:
                # Check if this looks like a portfolio query (no ticker)
                if not request.ticker or request.ticker.strip() == '':
                    portfolio_keywords = ['position', 'portfolio', 'holding', 'open', 'what do i have']
                    if any(keyword in user_input.lower() for keyword in portfolio_keywords):
                        raise ValueError(
                            f"Portfolio queries not yet supported. "
                            f"Please ask about a specific ticker (e.g., 'any positions in AAPL?')"
                        )

                raise ValueError(f"Invalid request: {request}")

            # Step 3: Strategy analysis
            analysis = await self.analyzer.analyze(request)
            logger.debug(
                f"Analysis complete: {analysis.signal.value} "
                f"with {analysis.confidence:.1%} confidence"
            )

            # Step 4: Risk assessment
            risk_assessment = await self.risk.assess(request, analysis, user_id)
            logger.debug(
                f"Risk assessment: {risk_assessment.recommended_quantity} shares, "
                f"{risk_assessment.portfolio_pct:.1f}% of portfolio"
            )

            # Step 5: Create suggestion
            suggestion = self._create_suggestion(request, analysis, risk_assessment)

            # Step 6: Save to session (if session store available)
            if self.session_store:
                await self.session_store.save_suggestion(user_id, suggestion)

            # Step 7: Return decision (awaiting user confirmation)
            decision = TradeDecision(
                suggestion=suggestion,
                approved=False,
                session_id=suggestion.suggestion_id,
                user_id=user_id,
            )

            logger.info(
                f"Suggestion created: {suggestion.signal.value} "
                f"{suggestion.recommended_quantity} shares {suggestion.ticker}"
            )

            return decision

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            raise

    async def execute_decision(
        self,
        decision: TradeDecision,
        modifications: Optional[dict] = None
    ) -> OrderResult:
        """
        Execute an approved trade decision.

        Args:
            decision: The trade decision (with approved=True)
            modifications: Optional modifications to quantity/price

        Returns:
            OrderResult with order IDs and execution details

        Raises:
            ValueError: If decision not approved or invalid modifications
        """
        if not decision.approved:
            raise ValueError("Cannot execute unapproved decision")

        logger.info(
            f"Executing decision for {decision.suggestion.ticker}: "
            f"{decision.suggestion.recommended_quantity} shares"
        )

        try:
            # Apply modifications if provided
            if modifications:
                decision = self._apply_modifications(decision, modifications)

            # Execute via execution manager
            result = await self.executor.execute_trade(
                decision.suggestion,
                decision
            )

            # Save to session (if available)
            if self.session_store:
                await self.session_store.save_execution(
                    decision.user_id,
                    decision,
                    result
                )

            logger.info(
                f"Execution complete: {result.success}, "
                f"entry_order={result.entry_order_id}"
            )

            return result

        except Exception as e:
            logger.error(f"Error executing trade: {e}", exc_info=True)
            raise

    def _create_suggestion(
        self,
        request: TradeRequest,
        analysis: AnalysisResult,
        risk_assessment: RiskAssessment
    ) -> TradeSuggestion:
        """
        Merge analysis and risk assessment into actionable suggestion.

        Args:
            request: Original trade request
            analysis: Strategy analysis result
            risk_assessment: Risk assessment result

        Returns:
            TradeSuggestion ready for user confirmation
        """
        # Generate unique suggestion ID
        suggestion_id = str(uuid.uuid4())[:8]

        # Use modified quantity if user specified, otherwise use risk manager's recommendation
        quantity = request.quantity if request.quantity else risk_assessment.recommended_quantity

        # Create suggestion
        suggestion = TradeSuggestion(
            # From analysis
            signal=analysis.signal,
            confidence=analysis.confidence,
            entry_price=analysis.entry_price,
            stop_loss=analysis.stop_loss,
            take_profit=analysis.take_profit,
            reasoning=analysis.reasoning,

            # From risk assessment
            recommended_quantity=quantity,
            portfolio_pct=risk_assessment.portfolio_pct,
            max_loss_usd=risk_assessment.max_loss_usd,
            risk_reward_ratio=risk_assessment.risk_reward_ratio,
            warnings=risk_assessment.warnings,

            # Order details
            ticker=request.ticker,
            order_type=OrderType.LIMIT,
            time_in_force=TimeInForce.GTC,  # Always GTC per requirements

            # Metadata
            suggestion_id=suggestion_id,
            timestamp=datetime.utcnow(),
        )

        return suggestion

    def _apply_modifications(
        self,
        decision: TradeDecision,
        modifications: dict
    ) -> TradeDecision:
        """
        Apply user modifications to a decision.

        Args:
            decision: Original decision
            modifications: Dict with keys: quantity, entry, stop, target

        Returns:
            Modified TradeDecision
        """
        if "quantity" in modifications:
            decision.modified_quantity = modifications["quantity"]

        if "entry" in modifications:
            decision.modified_entry = modifications["entry"]

        if "stop" in modifications:
            decision.modified_stop = modifications["stop"]

        if "target" in modifications:
            decision.modified_target = modifications["target"]

        decision.decision_timestamp = datetime.utcnow()

        return decision

    async def get_session_history(self, user_id: str, limit: int = 10) -> list:
        """
        Get recent suggestions for a user.

        Args:
            user_id: User ID
            limit: Number of recent suggestions to retrieve

        Returns:
            List of recent TradeSuggestion objects
        """
        if not self.session_store:
            return []

        return await self.session_store.get_recent_suggestions(user_id, limit)

    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if cancelled successfully
        """
        return await self.executor.cancel_order(order_id)

    async def get_order_status(self, order_id: str) -> dict:
        """
        Get status of an order.

        Args:
            order_id: Order ID

        Returns:
            Dict with order status details
        """
        return await self.executor.get_order_status(order_id)
