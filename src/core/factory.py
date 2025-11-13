"""
OrchestratorFactory - Creates fully wired TradingOrchestrator.

MVP: Hardcoded component creation (YAML config deferred to later iteration).
"""

import logging
import os
import json

from core.trading_orchestrator import TradingOrchestrator
from services.llm import OpenAIService
from parsers import LLMParser
from strategies import VoterStrategy, RealVoterStrategy
from risk import SimpleRiskManager
from execution import AlpacaExecutionManager

logger = logging.getLogger(__name__)

# Import existing OrderManager for real integration
try:
    from trading.alpaca_trading_client import AlpacaOrderManager
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logger.warning("AlpacaOrderManager not available - will use stub mode")


class OrchestratorFactory:
    """
    Factory to create fully wired TradingOrchestrator.

    MVP: Hardcoded dependencies (no YAML config yet).
    Components created with sensible defaults.
    """

    def __init__(self, config_path: str = "config/config.json"):
        """Initialize factory.

        Args:
            config_path: Path to config.json file
        """
        self.config_path = config_path
        self.config = self._load_config()
        logger.info("OrchestratorFactory initialized")

    def _load_config(self) -> dict:
        """Load configuration from config.json."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded config from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.warning(
                f"Config file not found: {self.config_path}, using environment variables")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return {}

    def create(self, order_manager=None, use_real_voter: bool = True,
               use_real_alpaca: bool = True, alpaca_mode: str = "paper") -> TradingOrchestrator:
        """
        Create TradingOrchestrator with all components wired.

        MVP: Hardcoded configuration.
        Future: Load from YAML config.

        Args:
            order_manager: Optional OrderManager for execution (None = auto-create or stub)
            use_real_voter: If True, use real VoterAgent with MACD+RSI analysis (default: True)
                          If False, use stub VoterStrategy for testing
            use_real_alpaca: If True, create real AlpacaOrderManager (default: True)
                           If False, use stub execution
            alpaca_mode: "paper" or "live" trading mode (default: "paper")

        Returns:
            Fully wired TradingOrchestrator ready to use
        """
        logger.info("Creating TradingOrchestrator with config from config.json...")

        # Load API key and models from config
        api_key = self.config.get("OPEN_AI_KEY") or os.getenv("OPENAI_API_KEY")
        tool_model = self.config.get("OPENAI_TOOL_MODEL", "gpt-4o-mini")
        reasoning_model = self.config.get("OPENAI_PROMPT_MODEL", "gpt-4o-mini")

        # 1. Create LLM Service
        logger.info(
            f"  - Creating OpenAIService (tool: {tool_model}, reasoning: {reasoning_model})...")
        llm_service = OpenAIService(
            tool_calling_model=tool_model,
            reasoning_model=reasoning_model,
            api_key=api_key
        )

        # 2. Create Input Parser
        logger.info("  - Creating LLMParser...")
        input_parser = LLMParser(llm_service=llm_service)

        # 3. Create Strategy Analyzer
        if use_real_voter:
            logger.info("  - Creating RealVoterStrategy (production MACD+RSI)...")
            strategy_analyzer = RealVoterStrategy(
                macd_params={'fast': 13, 'slow': 34, 'signal': 8},  # Validated Fibonacci parameters
                rsi_params={'period': 14, 'oversold': 30, 'overbought': 70},
                lookback_days=60
            )
        else:
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

        # Auto-create OrderManager if requested and not provided
        if order_manager is None and use_real_alpaca and ALPACA_AVAILABLE:
            logger.info(f"    Auto-creating AlpacaOrderManager (mode: {alpaca_mode})...")
            try:
                order_manager = AlpacaOrderManager(mode=alpaca_mode)
                logger.info(f"    ✅ AlpacaOrderManager created successfully")
            except Exception as e:
                logger.error(f"    ❌ Failed to create AlpacaOrderManager: {e}")
                logger.warning("    Falling back to stub mode")
                order_manager = None
        elif order_manager:
            logger.info("    Using provided OrderManager")
        else:
            logger.warning("    No OrderManager - using stub mode")

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
