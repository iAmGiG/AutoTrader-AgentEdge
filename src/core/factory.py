"""
OrchestratorFactory - Creates fully wired TradingOrchestrator.

MVP: Hardcoded component creation (YAML config deferred to later iteration).
"""

import logging
import os

from core.trading_orchestrator import TradingOrchestrator
from services.llm import OpenAIService
from parsers import LLMParser
from strategies import VoterStrategy
from risk import SimpleRiskManager
from execution import AlpacaExecutionManager


logger = logging.getLogger(__name__)


class OrchestratorFactory:
    """
    Factory to create fully wired TradingOrchestrator.

    MVP: Hardcoded dependencies (no YAML config yet).
    Components created with sensible defaults.
    """

    def __init__(self):
        """Initialize factory."""
        logger.info("OrchestratorFactory initialized")

    def create(self, order_manager=None) -> TradingOrchestrator:
        """
        Create TradingOrchestrator with all components wired.

        MVP: Hardcoded configuration.
        Future: Load from YAML config.

        Args:
            order_manager: Optional OrderManager for execution (None = stub mode)

        Returns:
            Fully wired TradingOrchestrator ready to use
        """
        logger.info("Creating TradingOrchestrator with hardcoded config...")

        # 1. Create LLM Service
        logger.info("  - Creating OpenAIService (gpt-4o-mini)...")
        llm_service = OpenAIService(
            tool_calling_model="gpt-4o-mini",
            reasoning_model="gpt-4o-mini",  # o3-mini is expensive
            api_key=os.getenv("OPENAI_API_KEY")
        )

        # 2. Create Input Parser
        logger.info("  - Creating LLMParser...")
        input_parser = LLMParser(llm_service=llm_service)

        # 3. Create Strategy Analyzer
        logger.info("  - Creating VoterStrategy (stub)...")
        strategy_analyzer = VoterStrategy()

        # 4. Create Risk Manager
        logger.info("  - Creating SimpleRiskManager...")
        risk_manager = SimpleRiskManager(
            account_service=None,  # Will use fallback ($100k portfolio)
            default_position_pct=5.0,
            max_position_pct=15.0
        )

        # 5. Create Execution Manager
        logger.info("  - Creating AlpacaExecutionManager...")
        if order_manager:
            logger.info("    Using provided OrderManager")
        else:
            logger.warning("    No OrderManager provided - stub mode")
        execution_manager = AlpacaExecutionManager(order_manager=order_manager)

        # 6. Create TradingOrchestrator
        logger.info("  - Wiring TradingOrchestrator...")
        orchestrator = TradingOrchestrator(
            input_parser=input_parser,
            strategy_analyzer=strategy_analyzer,
            risk_manager=risk_manager,
            execution_manager=execution_manager,
            session_store=None  # Optional, defer to later
        )

        logger.info("✅ TradingOrchestrator created successfully!")
        logger.info(f"   Parser: {type(input_parser).__name__}")
        logger.info(f"   Analyzer: {strategy_analyzer.name}")
        logger.info(f"   Risk: {type(risk_manager).__name__}")
        logger.info(f"   Executor: {type(execution_manager).__name__}")

        return orchestrator
