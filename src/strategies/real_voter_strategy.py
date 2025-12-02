"""
Real VoterStrategy - Wraps the production VoterAgent with MACD+RSI analysis.

This adapter integrates the validated VoterAgent (0.856 Sharpe ratio) into
the plugin architecture while handling market data fetching.
"""

import logging
from datetime import timedelta
from typing import Dict, Optional

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

        try:
            # 1. Get current timeframe setting
            timeframe_info = get_current_timeframe()
            user_timeframe = timeframe_info.get("current_timeframe", "1d")
            alpaca_timeframe = convert_to_alpaca_timeframe(user_timeframe)

            # Calculate appropriate lookback based on timeframe
            # Intraday timeframes need more calendar days to get enough bars
            if user_timeframe.endswith("m"):  # Minutes
                lookback_days = max(self.lookback_days, 14)  # At least 2 weeks for intraday
            elif user_timeframe.endswith("h"):  # Hours
                lookback_days = max(self.lookback_days, 30)  # At least 1 month for hourly
            else:  # Days, weeks, months
                lookback_days = self.lookback_days

            # 2. Fetch market data
            logger.info(
                f"Fetching market data for {ticker} ({lookback_days} days, {user_timeframe})..."
            )
            end_date = get_datetime_now().strftime("%Y-%m-%d")
            start_date = (get_datetime_now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

            # Catch API errors and convert to simple messages
            try:
                market_data = fetch_unified_market_data(
                    ticker,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe=alpaca_timeframe,
                )
            except Exception as api_error:
                # Log full API error for debugging
                logger.debug(f"API error fetching data for {ticker}: {api_error}", exc_info=True)
                # Return simple message to user
                raise ValueError("Ticker not found")

            if market_data is None or market_data.empty:
                logger.info(f"No market data returned for {ticker}")
                raise ValueError("Ticker not found")

            # Ensure Close column exists
            if "Close" not in market_data.columns and "close" in market_data.columns:
                market_data["Close"] = market_data["close"]

            if len(market_data) < 42:
                logger.info(f"Insufficient data for {ticker}: {len(market_data)} points (need 42+)")
                raise ValueError("Data unavailable")

            logger.info(f"✅ Loaded {len(market_data)} data points for {ticker}")

            # 2. Evaluate using VoterAgent
            result = self.voter.evaluate_voting(ticker, market_data, return_components=True)

            # 3. Convert VoterAgent result to AnalysisResult
            current_price = result.get("current_price", request.price or 0.0)

            # Map action to Signal enum
            signal_map = {"BUY": Signal.BUY, "SELL": Signal.SELL, "HOLD": Signal.HOLD}
            signal = signal_map.get(result["action"], Signal.HOLD)

            # Get exit percentages from config
            stop_loss_pct = self.config.get_risk_config("stop_loss")
            take_profit_pct = self.config.get_risk_config("take_profit")

            # Calculate entry/stop/target prices (rounded to cents for Alpaca)
            if signal == Signal.BUY:
                entry_price = round(current_price, 2)
                stop_loss = round(current_price * (1 - stop_loss_pct), 2)
                take_profit = round(current_price * (1 + take_profit_pct), 2)
            elif signal == Signal.SELL:
                entry_price = round(current_price, 2)
                stop_loss = round(current_price * (1 + stop_loss_pct), 2)  # inverse for shorts
                take_profit = round(current_price * (1 - take_profit_pct), 2)  # inverse for shorts
            else:
                # HOLD signal: no position, no entry/exit prices
                entry_price = None
                stop_loss = None
                take_profit = None

            # Build reasoning list
            reasoning = [result["reasoning"]]

            # Add timeframe context
            reasoning.append(f"Timeframe: {user_timeframe}")

            if "components" in result:
                macd = result["components"]["macd"]
                rsi = result["components"]["rsi"]
                reasoning.append(f"MACD: {macd['action']} (histogram: {macd['histogram']:.6f})")
                reasoning.append(f"RSI: {rsi['action']} (value: {rsi['value']:.1f})")

            # Add signal type context
            signal_type = result.get("signal_type", "UNKNOWN")
            if signal_type == "STRONG":
                reasoning.append("✅ Strong consensus between indicators")
            elif signal_type == "WEAK":
                reasoning.append("⚠️ Weak signal from single indicator")
            elif signal_type == "CONFLICT":
                reasoning.append("⚠️ Conflicting signals between indicators")

            return AnalysisResult(
                signal=signal,
                confidence=result["confidence"],
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reasoning=reasoning,
                indicators={
                    "macd_histogram": (
                        result["components"]["macd"]["histogram"] if "components" in result else 0.0
                    ),
                    "rsi_value": (
                        result["components"]["rsi"]["value"] if "components" in result else 50.0
                    ),
                    "signal_type": signal_type,
                    "position_size_multiplier": result.get("position_size", 1.0),
                    "timeframe": user_timeframe,
                },
                analyzer_name=self.name,
            )

        except ValueError:
            # Re-raise ValueError (user-friendly messages already set)
            raise
        except Exception as e:
            # Log unexpected errors and return generic message
            logger.error(f"Unexpected error analyzing {ticker}: {e}", exc_info=True)
            raise ValueError("Error processing request")

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
