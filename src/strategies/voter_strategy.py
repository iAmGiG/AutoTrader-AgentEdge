"""
VoterStrategy - Wraps existing VoterAgent into StrategyAnalyzer interface.

This adapter allows the proven VoterAgent (0.856 Sharpe ratio) to plug into
the new architecture without modification.
"""

import logging
from typing import Dict, Any

from src.core.interfaces import StrategyAnalyzer
from src.core.models import TradeRequest, AnalysisResult, Signal, AssetType
from src.autogen_agents.voter_agent import VoterAgent
from src.Utils.unified_cache_manager import UnifiedCacheManager


logger = logging.getLogger(__name__)


class VoterStrategy(StrategyAnalyzer):
    """
    MACD+RSI voting strategy (production-validated).

    Wraps the existing VoterAgent and integrates it with the new architecture.

    Performance (2024-2025 validated):
    - Sharpe Ratio: 0.856
    - Total Return: 36.6%
    - Win Rate: 51.4%
    - Max Drawdown: -10.10%
    """

    def __init__(
        self,
        cache_manager: UnifiedCacheManager,
        macd_params: Dict[str, int] = None,
        rsi_params: Dict[str, int] = None,
    ):
        """
        Initialize VoterStrategy.

        Args:
            cache_manager: UnifiedCacheManager for market data
            macd_params: Optional MACD parameters (defaults to validated 13/34/8)
            rsi_params: Optional RSI parameters (defaults to validated 14/30/70)
        """
        self.cache = cache_manager

        # Create VoterAgent with parameters
        self.voter_agent = VoterAgent(
            name="voter_strategy",
            macd_params=macd_params,
            rsi_params=rsi_params,
            use_config_file=True if not macd_params and not rsi_params else False
        )

        logger.info("VoterStrategy initialized with VoterAgent")

    async def analyze(self, request: TradeRequest) -> AnalysisResult:
        """
        Analyze trade request using MACD+RSI voting.

        Args:
            request: Trade request to analyze

        Returns:
            AnalysisResult with signal, confidence, entry/stop/target

        Raises:
            ValueError: If ticker invalid or insufficient data
        """
        ticker = request.ticker

        try:
            # Fetch price data from cache
            logger.info(f"Fetching data for {ticker}")
            price_data = await self._fetch_price_data(ticker)

            if price_data is None or price_data.empty:
                raise ValueError(f"No price data available for {ticker}")

            # Run VoterAgent evaluation
            result = self.voter_agent.evaluate_voting(
                symbol=ticker,
                price_data=price_data,
                return_components=True
            )

            # Convert VoterAgent result to AnalysisResult
            analysis = self._convert_to_analysis_result(ticker, result)

            logger.info(
                f"VoterStrategy analysis complete: {ticker} → {analysis.signal.value} "
                f"({analysis.confidence:.1%} confidence)"
            )

            return analysis

        except Exception as e:
            logger.error(f"Analysis error for {ticker}: {e}", exc_info=True)
            raise ValueError(f"Failed to analyze {ticker}: {e}") from e

    async def _fetch_price_data(self, ticker: str):
        """
        Fetch price data from cache manager.

        Args:
            ticker: Stock ticker

        Returns:
            DataFrame with price data
        """
        # Get recent bars (need ~60 for MACD with 34 slow period)
        bars = self.cache.get_cached_bars(ticker, timeframe="1Day", limit=100)

        if bars is None or bars.empty:
            # Try fetching if not cached
            bars = await self.cache.async_fetch_bars(
                ticker,
                timeframe="1Day",
                limit=100
            )

        return bars

    def _convert_to_analysis_result(
        self,
        ticker: str,
        voter_result: Dict[str, Any]
    ) -> AnalysisResult:
        """
        Convert VoterAgent result to AnalysisResult.

        Args:
            ticker: Stock ticker
            voter_result: Result from VoterAgent.evaluate_voting()

        Returns:
            AnalysisResult
        """
        # Extract signal from VoterAgent
        action = voter_result.get("action", "HOLD").upper()
        signal_map = {
            "BUY": Signal.BUY,
            "SELL": Signal.SELL,
            "HOLD": Signal.HOLD
        }
        signal = signal_map.get(action, Signal.HOLD)

        # Extract confidence
        confidence = voter_result.get("confidence", 0.5)

        # Get current price from voter result
        current_price = voter_result.get("current_price", 0.0)

        # Calculate entry/stop/target based on signal
        if signal == Signal.BUY:
            entry_price = current_price
            stop_loss = current_price * 0.98  # -2% stop
            take_profit = current_price * 1.035  # +3.5% target
        elif signal == Signal.SELL:
            entry_price = current_price
            stop_loss = current_price * 1.02  # +2% stop (for short)
            take_profit = current_price * 0.965  # -3.5% target (for short)
        else:  # HOLD
            entry_price = current_price
            stop_loss = current_price
            take_profit = current_price

        # Extract reasoning
        reasoning = []

        # MACD reasoning
        macd_signal = voter_result.get("macd_signal", "HOLD")
        macd_hist = voter_result.get("macd_histogram", 0.0)
        reasoning.append(
            f"MACD: {macd_signal} (histogram: {macd_hist:.3f})"
        )

        # RSI reasoning
        rsi_signal = voter_result.get("rsi_signal", "HOLD")
        rsi_value = voter_result.get("rsi_value", 50.0)
        reasoning.append(
            f"RSI: {rsi_signal} (value: {rsi_value:.1f})"
        )

        # Consensus
        is_consensus = voter_result.get("is_consensus", False)
        if is_consensus:
            reasoning.append("✅ MACD + RSI consensus (high confidence)")

        # Build indicators dict
        indicators = {
            "macd_signal": macd_signal,
            "macd_histogram": macd_hist,
            "rsi_signal": rsi_signal,
            "rsi_value": rsi_value,
            "is_consensus": is_consensus,
        }

        return AnalysisResult(
            signal=signal,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reasoning=reasoning,
            indicators=indicators,
            analyzer_name="VoterStrategy (MACD+RSI)"
        )

    @property
    def name(self) -> str:
        return "VoterStrategy"

    @property
    def supported_asset_types(self) -> list:
        return [AssetType.STOCK]  # Stocks only (options in #330)
