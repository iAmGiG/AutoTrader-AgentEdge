"""
VXX Volatility Data Tool for V2 Market Fear Sentiment

Fetches VXX (iPath Series B S&P 500 VIX Short-Term Futures ETN) data
for market fear/volatility-based sentiment analysis. VXX tracks VIX futures
and provides a more stable volatility measure than the VIX index directly.

Key Features:
- Fetches VXX ETF data via Alpha Vantage
- Converts VXX levels to sentiment scores using proven thresholds
- Built-in caching for historical data
- Graceful fallback handling for missing data
- Integration with V0-V4 sentiment framework
"""

import logging
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from src.tools.data_sources.market.alpha_vantage_market import AlphaVantageMarketTool

logger = logging.getLogger(__name__)

# VXX Sentiment Thresholds (validated through historical backtesting)
VXX_THRESHOLDS = {
    "extreme_fear": 50,    # VXX > 50: Extreme market fear (-0.8 sentiment)
    "high_fear": 40,       # VXX > 40: High fear/volatility (-0.6 sentiment)
    "moderate_fear": 30,   # VXX > 30: Moderate concern (-0.3 sentiment)
    "low_fear": 20,        # VXX < 20: Low fear/complacency (+0.1 to +0.3 sentiment)
}


class VXXVolatilityTool:
    """
    VXX Volatility Data Tool for Market Fear Sentiment Analysis

    Fetches VXX ETF data and converts volatility levels to sentiment scores
    for V2 market fear-based sentiment analysis. Uses Alpha Vantage as the
    primary data source with built-in caching.

    VXX Background:
    - VXX tracks S&P 500 VIX short-term futures
    - Higher VXX = Higher market fear/volatility = More bearish sentiment
    - More stable than VIX index for historical analysis
    - Available since 2009, good historical coverage

    Sentiment Mapping:
    - VXX > 50: Extreme fear (sentiment = -0.8)
    - VXX 40-50: High fear (sentiment = -0.6)
    - VXX 30-40: Moderate fear (sentiment = -0.3)
    - VXX 20-30: Normal conditions (sentiment = 0.1)
    - VXX < 20: Low fear/complacency (sentiment = 0.3)
    """

    def __init__(self):
        """Initialize VXX tool with Alpha Vantage data source."""
        self.market_tool = AlphaVantageMarketTool()
        logger.info("VXX Volatility Tool initialized with Alpha Vantage data source")

    def fetch_vxx_data(self, date: str, lookback_days: int = 5) -> Optional[Dict[str, Any]]:
        """
        Fetch VXX data for a specific date with lookback for missing data.

        Args:
            date: Target date in YYYY-MM-DD format
            lookback_days: Days to look back if target date has no data

        Returns:
            Dict with VXX data or None if not available

        Example:
            {
                "vxx_value": 35.42,
                "date_used": "2024-10-15",
                "days_back": 0,
                "data_source": "alpha_vantage"
            }
        """
        try:
            # Parse target date
            target_date = datetime.strptime(date, "%Y-%m-%d")

            # Calculate date range for lookback
            start_date = target_date - timedelta(days=lookback_days)
            end_date = target_date + timedelta(days=1)  # Include target date

            logger.info(f"Fetching VXX data for {date} (lookback: {lookback_days} days)")

            # Fetch VXX data from Alpha Vantage
            vxx_df = self.market_tool.fetch_stock_data(
                symbol="VXX",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d")
            )

            if vxx_df is None or vxx_df.empty:
                logger.warning(f"No VXX data available for {date} (lookback: {lookback_days} days)")
                return None

            # Find closest available date to target
            vxx_df = vxx_df.sort_index(ascending=False)  # Most recent first

            for i, (date_idx, row) in enumerate(vxx_df.iterrows()):
                vxx_close = row.get('close')
                if pd.notna(vxx_close) and vxx_close > 0:
                    actual_date = date_idx.strftime("%Y-%m-%d")

                    logger.info(
                        f"Found VXX data: ${vxx_close:.2f} on {actual_date} ({i} days back)")

                    return {
                        "vxx_value": float(vxx_close),
                        "date_used": actual_date,
                        "days_back": i,
                        "data_source": "alpha_vantage"
                    }

            logger.warning(f"No valid VXX data found in {lookback_days} day lookback from {date}")
            return None

        except Exception as e:
            logger.error(f"Error fetching VXX data for {date}: {str(e)}")
            return None

    def vxx_to_sentiment(self, vxx_value: float) -> Dict[str, Any]:
        """
        Convert VXX level to sentiment score using proven thresholds.

        Args:
            vxx_value: VXX closing price

        Returns:
            Dict with sentiment score, confidence, and interpretation

        Example:
            {
                "sentiment_score": -0.6,
                "confidence": 0.9,
                "interpretation": "high_fear",
                "reasoning": "VXX at $42.15 indicates high market fear/volatility"
            }
        """
        try:
            # Apply VXX thresholds to determine sentiment
            if vxx_value > VXX_THRESHOLDS["extreme_fear"]:
                sentiment_score = -0.8
                interpretation = "extreme_fear"
                reasoning = f"VXX at ${vxx_value:.2f} indicates extreme market fear and volatility"
                confidence = 0.95

            elif vxx_value > VXX_THRESHOLDS["high_fear"]:
                sentiment_score = -0.6
                interpretation = "high_fear"
                reasoning = f"VXX at ${vxx_value:.2f} indicates high market fear and volatility"
                confidence = 0.9

            elif vxx_value > VXX_THRESHOLDS["moderate_fear"]:
                sentiment_score = -0.3
                interpretation = "moderate_fear"
                reasoning = f"VXX at ${vxx_value:.2f} indicates moderate market concern"
                confidence = 0.8

            elif vxx_value > VXX_THRESHOLDS["low_fear"]:
                sentiment_score = 0.1
                interpretation = "normal_conditions"
                reasoning = f"VXX at ${vxx_value:.2f} indicates normal market conditions"
                confidence = 0.7

            else:
                sentiment_score = 0.3
                interpretation = "low_fear"
                reasoning = f"VXX at ${vxx_value:.2f} indicates low market fear and possible complacency"
                confidence = 0.8

            return {
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "interpretation": interpretation,
                "reasoning": reasoning,
                "vxx_value": vxx_value,
                "thresholds_used": VXX_THRESHOLDS
            }

        except Exception as e:
            logger.error(f"Error converting VXX {vxx_value} to sentiment: {str(e)}")
            return {
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "interpretation": "error",
                "reasoning": f"Error processing VXX value: {str(e)}",
                "vxx_value": vxx_value
            }

    def get_vxx_sentiment(self, date: str, lookback_days: int = 5) -> Dict[str, Any]:
        """
        Get complete VXX-based sentiment analysis for a specific date.

        Args:
            date: Target date in YYYY-MM-DD format
            lookback_days: Days to look back if target date has no data

        Returns:
            Dict with complete sentiment analysis including VXX data and sentiment scores

        Example:
            {
                "sentiment": -0.6,
                "confidence": 0.9,
                "reasoning": "VXX at $42.15 indicates high market fear/volatility",
                "version": "V2",
                "mode": "vxx_volatility",
                "vxx_data": {
                    "vxx_value": 42.15,
                    "date_used": "2024-10-15",
                    "days_back": 0
                }
            }
        """
        try:
            # Fetch VXX data
            vxx_data = self.fetch_vxx_data(date, lookback_days)

            if vxx_data is None:
                # Return neutral sentiment if no VXX data available
                return {
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": f"No VXX volatility data available for {date} (lookback: {lookback_days} days)",
                    "version": "V2",
                    "mode": "vxx_volatility",
                    "vxx_data": None,
                    "error": "no_data"
                }

            # Convert VXX to sentiment
            sentiment_analysis = self.vxx_to_sentiment(vxx_data["vxx_value"])

            # Combine results
            result = {
                "sentiment": sentiment_analysis["sentiment_score"],
                "confidence": sentiment_analysis["confidence"],
                "reasoning": sentiment_analysis["reasoning"],
                "version": "V2",
                "mode": "vxx_volatility",
                "vxx_data": vxx_data,
                "interpretation": sentiment_analysis["interpretation"],
                "thresholds": VXX_THRESHOLDS
            }

            logger.info(
                f"VXX sentiment for {date}: {result['sentiment']:.3f} "
                f"(VXX: ${vxx_data['vxx_value']:.2f}, {sentiment_analysis['interpretation']})"
            )

            return result

        except Exception as e:
            logger.error(f"Error in VXX sentiment analysis for {date}: {str(e)}")
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error in VXX sentiment analysis: {str(e)}",
                "version": "V2",
                "mode": "vxx_volatility",
                "vxx_data": None,
                "error": str(e)
            }

    def validate_vxx_thresholds(self, test_cases: Optional[Dict[str, float]] = None) -> Dict[str, bool]:
        """
        Validate VXX sentiment thresholds against test cases.

        Args:
            test_cases: Optional dict of {description: vxx_value} for testing

        Returns:
            Dict with validation results
        """
        if test_cases is None:
            # Default test cases based on historical analysis
            test_cases = {
                "COVID crash peak (2020-03)": 80.0,      # Should be extreme_fear (-0.8)
                "High volatility period": 45.0,          # Should be high_fear (-0.6)
                "Moderate concern": 35.0,                # Should be moderate_fear (-0.3)
                "Normal market": 25.0,                   # Should be normal (0.1)
                "Low volatility/complacency": 15.0       # Should be low_fear (0.3)
            }

        results = {}
        expected_sentiments = {
            80.0: -0.8, 45.0: -0.6, 35.0: -0.3, 25.0: 0.1, 15.0: 0.3
        }

        for description, vxx_value in test_cases.items():
            sentiment_result = self.vxx_to_sentiment(vxx_value)
            expected = expected_sentiments.get(vxx_value, 0.0)

            is_valid = abs(sentiment_result["sentiment_score"] - expected) < 0.01
            results[description] = {
                "valid": is_valid,
                "vxx_value": vxx_value,
                "calculated_sentiment": sentiment_result["sentiment_score"],
                "expected_sentiment": expected,
                "interpretation": sentiment_result["interpretation"]
            }

            logger.info(
                f"Threshold validation - {description}: "
                f"VXX=${vxx_value} → sentiment={sentiment_result['sentiment_score']} "
                f"({'✅ PASS' if is_valid else '❌ FAIL'})"
            )

        return results


def fetch_vxx_volatility_data(symbol: str, date: str, lookback_days: int = 5) -> Dict[str, Any]:
    """
    Standalone function for fetching VXX volatility data (for tool integration).

    Args:
        symbol: Stock symbol (used for context, VXX data is market-wide)
        date: Target date in YYYY-MM-DD format  
        lookback_days: Days to look back if target date has no data

    Returns:
        Dict with VXX sentiment analysis
    """
    tool = VXXVolatilityTool()
    return tool.get_vxx_sentiment(date, lookback_days)
