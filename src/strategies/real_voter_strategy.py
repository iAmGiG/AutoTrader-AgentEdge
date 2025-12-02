"""
Real VoterStrategy - Wraps the production VoterAgent with MACD+RSI analysis.

This adapter integrates the validated VoterAgent (0.856 Sharpe ratio) into
the plugin architecture while handling market data fetching.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from config_defaults.trading_config import TradingConfig

from src.autogen_agents.voter_agent import VoterAgent
from src.core.interfaces.strategy_analyzer import StrategyAnalyzer
from src.core.models import AnalysisResult, AssetType, Signal, TradeRequest
from src.data_sources.tools import fetch_unified_market_data
from src.trading.timeframe_tools import (
    convert_to_alpaca_timeframe,
    get_current_timeframe,
)
from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)


class RealVoterStrategy(StrategyAnalyzer):
    """
    Production VoterStrategy using real MACD+RSI analysis.

    Features:
    - Validated VoterAgent with 0.856 Sharpe ratio
    - Real market data fetching (Alpaca, Polygon, Alpha Vantage)
    - MACD(13/34/8) + RSI(14) voting system
    - Confidence-based position sizing
    """

    def __init__(
        self,
        macd_params: Optional[Dict[str, int]] = None,
        rsi_params: Optional[Dict[str, int]] = None,
        lookback_days: int = 60,
    ):
        """
        Initialize RealVoterStrategy.

        Args:
            macd_params: MACD parameters (default: {fast: 13, slow: 34, signal: 8})
            rsi_params: RSI parameters (default: {period: 14, oversold: 30, overbought: 70})
            lookback_days: Days of historical data to fetch (default: 60)
        """
        # Use validated production parameters by default
        self.macd_params = macd_params or {"fast": 13, "slow": 34, "signal": 8}
        self.rsi_params = rsi_params or {"period": 14, "oversold": 30, "overbought": 70}
        self.lookback_days = lookback_days

        # Load trading config
        self.config = TradingConfig()

        # Create VoterAgent
        self.voter = VoterAgent(
            name="real_voter_strategy",
            macd_params=self.macd_params,
            rsi_params=self.rsi_params,
            use_config_file=True,
        )

        logger.info(
            f"RealVoterStrategy initialized with MACD({self.macd_params['fast']}/{self.macd_params['slow']}/{self.macd_params['signal']}) + RSI({self.rsi_params['period']})"
        )

    @property
    def name(self) -> str:
        """Strategy name."""
        return "VoterStrategy (MACD+RSI)"

    @property
    def supported_asset_types(self) -> list:
        """Currently supports stocks only."""
        return [AssetType.STOCK]

    async def analyze(self, request: TradeRequest) -> AnalysisResult:  # noqa: C901
        """
        Analyze trade request using MACD+RSI voting.

        Args:
            request: Trade request with ticker and optional price

        Returns:
            AnalysisResult with signal, confidence, entry/stop/target, and reasoning
        """
        ticker = request.ticker

        # This method now orchestrates the analysis by calling helper methods.
        # It makes the logic flow clearer and prepares for more complex agent interactions.
        try:
            user_timeframe, market_data = self._fetch_and_prepare_data(ticker)

            # In a future autogen implementation, this would initiate a chat.
            # For now, it calls the evaluation method directly.
            # Example:
            # prompt = f"Analyze {ticker} for a trade signal using MACD and RSI on a {user_timeframe} timeframe."
            # agent_response = user_proxy.initiate_chat(self.voter, message=prompt, market_data=market_data)
            # result = self._parse_agent_response(agent_response)

            result = self.voter.evaluate_voting(ticker, market_data, return_components=True)

            return self._format_analysis_result(result, request, user_timeframe)
        except ValueError:
            # Re-raise ValueError (user-friendly messages already set)
            raise
        except Exception as e:
            # Log unexpected errors and return generic message
            logger.error(f"Unexpected error analyzing {ticker}: {e}", exc_info=True)
            raise ValueError("Error processing request")

    def _fetch_and_prepare_data(self, ticker: str) -> tuple[str, Any]:
        """
        Fetches and validates market data for the given ticker.

        Returns:
            Tuple of (user_timeframe, market_data)
        """
        # 1. Get timeframe and calculate lookback
        timeframe_info = get_current_timeframe()
        user_timeframe = timeframe_info.get("current_timeframe", "1d")
        alpaca_timeframe = convert_to_alpaca_timeframe(user_timeframe)

        lookback_days = self.lookback_days
        if user_timeframe.endswith("m"):
            lookback_days = max(self.lookback_days, 14)
        elif user_timeframe.endswith("h"):
            lookback_days = max(self.lookback_days, 30)

        # 2. Fetch market data
        logger.info(
            f"Fetching market data for {ticker} ({lookback_days} days, {user_timeframe})..."
        )
        end_date = get_datetime_now().strftime("%Y-%m-%d")
        start_date = (get_datetime_now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        try:
            market_data = fetch_unified_market_data(
                ticker, start_date=start_date, end_date=end_date, timeframe=alpaca_timeframe
            )
        except Exception as api_error:
            logger.debug(f"API error fetching data for {ticker}: {api_error}", exc_info=True)
            raise ValueError("Ticker not found")

        if market_data is None or market_data.empty:
            logger.info(f"No market data returned for {ticker}")
            raise ValueError("Ticker not found")

        if "Close" not in market_data.columns and "close" in market_data.columns:
            market_data["Close"] = market_data["close"]

        if len(market_data) < 42:
            logger.info(f"Insufficient data for {ticker}: {len(market_data)} points (need 42+)")
            raise ValueError("Data unavailable")

        logger.info(f"✅ Loaded {len(market_data)} data points for {ticker}")
        return user_timeframe, market_data

    def _format_analysis_result(
        self, result: Dict[str, Any], request: TradeRequest, user_timeframe: str
    ) -> AnalysisResult:
        """Converts the agent's raw result into a structured AnalysisResult."""
        signal_map = {"BUY": Signal.BUY, "SELL": Signal.SELL, "HOLD": Signal.HOLD}
        signal = signal_map.get(result["action"], Signal.HOLD)
        current_price = result.get("current_price", request.price or 0.0)

        # Calculate entry/stop/target prices
        entry_price, stop_loss, take_profit = self._calculate_price_levels(signal, current_price)

        # Build reasoning list
        reasoning = self._build_reasoning_list(result, user_timeframe)

        # Extract indicators
        indicators = self._extract_indicators(result, user_timeframe)

        return AnalysisResult(
            signal=signal,
            confidence=result["confidence"],
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            indicators=indicators,
            analyzer_name=self.name,
        )

    def _calculate_price_levels(
        self, signal: Signal, current_price: float
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Calculates entry, stop loss, and take profit based on the signal.

        Returns:
            Tuple of (entry_price, stop_loss, take_profit)
        """
        if signal == Signal.HOLD:
            return None, None, None

        stop_loss_pct = self.config.get_risk_config("stop_loss")
        take_profit_pct = self.config.get_risk_config("take_profit")
        entry_price = round(current_price, 2)

        if signal == Signal.BUY:
            stop_loss = round(current_price * (1 - stop_loss_pct), 2)
            take_profit = round(current_price * (1 + take_profit_pct), 2)
        else:  # SELL
            stop_loss = round(current_price * (1 + stop_loss_pct), 2)
            take_profit = round(current_price * (1 - take_profit_pct), 2)

        return entry_price, stop_loss, take_profit

    def _build_reasoning_list(self, result: Dict[str, Any], user_timeframe: str) -> list[str]:
        """Constructs the human-readable reasoning for the analysis."""
        reasoning = [result["reasoning"], f"Timeframe: {user_timeframe}"]

        if "components" in result:
            macd = result["components"]["macd"]
            rsi = result["components"]["rsi"]
            reasoning.append(f"MACD: {macd['action']} (histogram: {macd['histogram']:.6f})")
            reasoning.append(f"RSI: {rsi['action']} (value: {rsi['value']:.1f})")

        signal_type = result.get("signal_type", "UNKNOWN")
        if signal_type == "STRONG":
            reasoning.append("✅ Strong consensus between indicators")
        elif signal_type == "WEAK":
            reasoning.append("⚠️ Weak signal from single indicator")
        elif signal_type == "CONFLICT":
            reasoning.append("⚠️ Conflicting signals between indicators")

        return reasoning

    def _extract_indicators(self, result: Dict[str, Any], user_timeframe: str) -> Dict[str, Any]:
        """Extracts key indicator values for logging and further analysis."""
        components = result.get("components", {})
        macd = components.get("macd", {})
        rsi = components.get("rsi", {})

        return {
            "macd_histogram": macd.get("histogram", 0.0),
            "rsi_value": rsi.get("value", 50.0),
            "signal_type": result.get("signal_type", "UNKNOWN"),
            "position_size_multiplier": result.get("position_size", 1.0),
            "timeframe": user_timeframe,
        }

    def _create_fallback_result(self, reason: str) -> AnalysisResult:
        """Create fallback result when analysis fails."""
        return AnalysisResult(
            signal=Signal.HOLD,
            confidence=0.0,
            entry_price=None,
            stop_loss=None,
            take_profit=None,
            reasoning=[f"⚠️ {reason}", "Defaulting to HOLD with no position"],
            indicators={"error": reason},
            analyzer_name=f"{self.name} (Fallback)",
        )
