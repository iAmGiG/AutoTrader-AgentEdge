"""
Real VoterStrategy - Wraps the production VoterAgent with MACD+RSI analysis.

This adapter integrates the validated VoterAgent (0.856 Sharpe ratio) into
the plugin architecture while handling market data fetching.
"""

import logging
import os
import sys
from datetime import datetime, timedelta  # TODO date_utils
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config_defaults.trading_config import TradingConfig

from src.autogen_agents.voter_agent import VoterAgent
from src.core.interfaces.strategy_analyzer import StrategyAnalyzer
from src.core.models import AnalysisResult, AssetType, Signal, TradeRequest
from src.data_sources.tools import fetch_unified_market_data

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

    async def analyze(self, request: TradeRequest) -> AnalysisResult:
        """
        Analyze trade request using MACD+RSI voting.

        Args:
            request: Trade request with ticker and optional price

        Returns:
            AnalysisResult with signal, confidence, entry/stop/target, and reasoning
        """
        ticker = request.ticker

        try:
            # 1. Fetch market data
            logger.info(f"Fetching market data for {ticker} ({self.lookback_days} days)...")
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime("%Y-%m-%d")

            market_data = fetch_unified_market_data(
                ticker, start_date=start_date, end_date=end_date
            )

            if market_data is None or market_data.empty:
                logger.warning(f"No market data available for {ticker}")
                return self._create_fallback_result(
                    ticker, request.price, "No market data available"
                )

            # Ensure Close column exists
            if "Close" not in market_data.columns and "close" in market_data.columns:
                market_data["Close"] = market_data["close"]

            if len(market_data) < 42:
                logger.warning(
                    f"Insufficient data for {ticker}: {len(market_data)} points (need 42+)"
                )
                return self._create_fallback_result(
                    ticker, request.price, f"Insufficient data ({len(market_data)} points)"
                )

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
                entry_price = round(current_price, 2)
                stop_loss = round(current_price * (1 - stop_loss_pct), 2)
                take_profit = round(current_price * (1 + take_profit_pct), 2)

            # Build reasoning list
            reasoning = [result["reasoning"]]

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
                },
                analyzer_name=self.name,
            )

        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}", exc_info=True)
            return self._create_fallback_result(ticker, request.price, f"Analysis error: {str(e)}")

    def _create_fallback_result(
        self, ticker: str, price: Optional[float], reason: str
    ) -> AnalysisResult:
        """Create fallback result when analysis fails."""
        current_price = price if price else 100.0

        # Use minimal safe stop/profit for fallback
        stop_loss_pct = self.config.get_risk_config("stop_loss")
        take_profit_pct = self.config.get_risk_config("take_profit")

        return AnalysisResult(
            signal=Signal.HOLD,
            confidence=0.0,
            entry_price=current_price,
            stop_loss=current_price * (1 - stop_loss_pct),
            take_profit=current_price * (1 + take_profit_pct),
            reasoning=[f"⚠️ {reason}", "Defaulting to HOLD with no position"],
            indicators={"error": reason},
            analyzer_name=f"{self.name} (Fallback)",
        )
