"""
OrchestratorFactory - Creates fully wired TradingOrchestrator.

MVP: Hardcoded component creation (YAML config deferred to later iteration).
Issue #400: Trading modes integration.
Issue #406: Uses AutoGen's native LLM client instead of custom OpenAIService.
"""

import json
import logging
from typing import Optional

from src.core.trading_modes import TradingMode, get_mode_manager
from src.core.trading_orchestrator import TradingOrchestrator
from src.parsers import AutoGenLLMParser
from src.strategies import RealVoterStrategy, VoterStrategy
from src.trading.broker.alpaca_execution_manager import AlpacaExecutionManager
from src.trading.risk.simple_risk_manager import SimpleRiskManager

logger = logging.getLogger(__name__)

# Import existing OrderManager for real integration
try:
    from src.trading.broker.alpaca_trading_client import AlpacaOrderManager

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
            with open(self.config_path, "r") as f:
                config = json.load(f)
            logger.info(f"Loaded config from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.warning(
                f"Config file not found: {self.config_path}, using environment variables"
            )
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return {}

    def create(
        self,
        order_manager=None,
        use_real_voter: bool = True,
        use_real_alpaca: bool = True,
        alpaca_mode: str = "paper",
        trading_mode: Optional[TradingMode] = None,
    ) -> TradingOrchestrator:
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
            trading_mode: Trading mode (conservative/moderate/aggressive) - Issue #400

        Returns:
            Fully wired TradingOrchestrator ready to use
        """
        # Initialize trading mode manager (Issue #400)
        mode_manager = get_mode_manager()
        if trading_mode:
            mode_manager.set_mode(trading_mode)
        mode_params = mode_manager.get_parameters()

        logger.info(
            f"Creating TradingOrchestrator (mode: {mode_params.mode.value}) from config.json..."
        )

        # Load API key and model from config (used by AutoGenLLMParser)
        tool_model = self.config.get("OPENAI_TOOL_MODEL", "gpt-4o-mini")

        # 1. Create Input Parser using AutoGen's native LLM client (#406)
        logger.info(f"  - Creating AutoGenLLMParser (model: {tool_model})...")
        input_parser = AutoGenLLMParser(model=tool_model)

        # 2. Create Strategy Analyzer
        if use_real_voter:
            logger.info("  - Creating RealVoterStrategy (production MACD+RSI)...")
            strategy_analyzer = RealVoterStrategy(
                macd_params={"fast": 13, "slow": 34, "signal": 8},  # Validated Fibonacci parameters
                rsi_params={"period": 14, "oversold": 30, "overbought": 70},
                lookback_days=90,  # Increased from 60 to ensure 42+ trading days (accounting for weekends/holidays)
            )
        else:
            logger.info("  - Creating VoterStrategy (stub)...")
            strategy_analyzer = VoterStrategy()

        # 3. Create Risk Manager (using trading mode parameters - Issue #400)
        logger.info(
            f"  - Creating SimpleRiskManager "
            f"(position: {mode_params.max_position_pct:.0%}, "
            f"portfolio: {mode_params.max_portfolio_pct:.0%})..."
        )
        risk_manager = SimpleRiskManager(
            account_service=None,  # Will use fallback ($100k portfolio)
            default_position_pct=mode_params.risk_per_trade * 100,  # Convert to percentage
            max_position_pct=mode_params.max_position_pct * 100,  # Convert to percentage
        )

        # 4. Create Execution Manager
        logger.info("  - Creating AlpacaExecutionManager...")

        # Auto-create OrderManager if requested and not provided
        if order_manager is None and use_real_alpaca and ALPACA_AVAILABLE:
            logger.info(f"    Auto-creating AlpacaOrderManager (mode: {alpaca_mode})...")
            try:
                order_manager = AlpacaOrderManager(mode=alpaca_mode)
                logger.info("    ✅ AlpacaOrderManager created successfully")
            except Exception as e:
                logger.error(f"    ❌ Failed to create AlpacaOrderManager: {e}")
                logger.warning("    Falling back to stub mode")
                order_manager = None
        elif order_manager:
            logger.info("    Using provided OrderManager")
        else:
            logger.warning("    No OrderManager - using stub mode")

        execution_manager = AlpacaExecutionManager(order_manager=order_manager)

        # 5. Create TradingOrchestrator
        logger.info("  - Wiring TradingOrchestrator...")
        orchestrator = TradingOrchestrator(
            input_parser=input_parser,
            strategy_analyzer=strategy_analyzer,
            risk_manager=risk_manager,
            execution_manager=execution_manager,
            session_store=None,  # Optional, defer to later
        )

        logger.info("TradingOrchestrator created successfully!")
        logger.info(f"   Mode: {mode_params.mode.value} ({mode_params.description})")
        logger.info(f"   Parser: {type(input_parser).__name__}")
        logger.info(f"   Analyzer: {strategy_analyzer.name}")
        logger.info(f"   Risk: {type(risk_manager).__name__}")
        logger.info(f"   Executor: {type(execution_manager).__name__}")

        # Store mode manager reference for later access
        orchestrator._mode_manager = mode_manager  # noqa: W0212

        return orchestrator
