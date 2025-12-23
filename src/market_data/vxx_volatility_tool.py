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
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd

from .alpha_vantage_market import AlphaVantageMarketTool

logger = logging.getLogger(__name__)

# VXX Contrarian Sentiment Thresholds - "Buy Fear, Sell Greed"
# VXX is a CONTRARIAN indicator: High VXX = Buy opportunity, Low VXX = Sell signal
VXX_THRESHOLDS = {
    "extreme_fear": 50,  # VXX > 50: Extreme fear = STRONG BUY (+0.8 sentiment)
    "high_fear": 40,  # VXX > 40: High fear = Buy opportunity (+0.6 sentiment)
    "moderate_fear": 30,  # VXX > 30: Moderate fear = Mild bullish (+0.3 sentiment)
    "low_fear": 20,  # VXX < 20: Low fear/complacency = Caution (-0.1 to -0.3 sentiment)
}


class VXXVolatilityTool:
    """
    VXX Volatility Data Tool for Market Fear Sentiment Analysis

    Fetches VXX ETF data and converts volatility levels to sentiment scores
    for V2 market fear-based sentiment analysis. Uses Alpha Vantage as the
    primary data source with built-in caching.

    VXX Background:
    - VXX tracks S&P 500 VIX short-term futures
    - Higher VXX = Higher market fear/volatility = CONTRARIAN BUY SIGNAL
    - More stable than VIX index for historical analysis
    - Available since 2009, good historical coverage

    Contrarian Sentiment Mapping ("Buy Fear, Sell Greed"):
    - VXX > 50: Extreme fear = STRONG BUY (sentiment = +0.8)
    - VXX 40-50: High fear = Buy opportunity (sentiment = +0.6)
    - VXX 30-40: Moderate fear = Mild bullish (sentiment = +0.3)
    - VXX 20-30: Normal conditions (sentiment = 0.1)
    - VXX < 20: Low fear/complacency = Caution (sentiment = -0.3)
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
                end_date=end_date.strftime("%Y-%m-%d"),
            )

            if vxx_df is None or vxx_df.empty:
                logger.warning(f"No VXX data available for {date} (lookback: {lookback_days} days)")
                return None

            # Find closest available date to target
            vxx_df = vxx_df.sort_index(ascending=False)  # Most recent first

            for i, (date_idx, row) in enumerate(vxx_df.iterrows()):
                vxx_close = row.get("close")
                if pd.notna(vxx_close) and vxx_close > 0:
                    actual_date = date_idx.strftime("%Y-%m-%d")

                    logger.info(
                        f"Found VXX data: ${vxx_close:.2f} on {actual_date} ({i} days back)"
                    )

                    return {
                        "vxx_value": float(vxx_close),
                        "date_used": actual_date,
                        "days_back": i,
                        "data_source": "alpha_vantage",
                    }

            logger.warning(f"No valid VXX data found in {lookback_days} day lookback from {date}")
            return None

        except Exception as e:
            logger.error(f"Error fetching VXX data for {date}: {str(e)}")
            return None

    def fetch_vxx_history(self, date: str, history_days: int = 30) -> Optional[pd.DataFrame]:
        """
        Fetch VXX historical data for percentile analysis.

        Uses SHORT lookback (30 days max) to avoid structural decay distortion.
        VXX decays ~0.5-1% per week due to futures contango, making long
        historical comparisons meaningless.

        Args:
            date: Target date in YYYY-MM-DD format
            history_days: Days of history (60 days optimal, max 90 to avoid decay issues)
        Returns:
            DataFrame with VXX historical data or None
        """
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = target_date - timedelta(days=history_days + 10)  # Buffer for weekends
            end_date = target_date + timedelta(days=1)

            logger.info(f"Fetching VXX history: {history_days} days from {date}")

            vxx_df = self.market_tool.fetch_stock_data(
                symbol="VXX",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )

            if vxx_df is None or vxx_df.empty:
                logger.warning(f"No VXX historical data available for {date}")
                return None

            # Get only the most recent history_days of data
            vxx_df = vxx_df.sort_index(ascending=False).head(history_days)
            return vxx_df

        except Exception as e:
            logger.error(f"Error fetching VXX history for {date}: {str(e)}")
            return None

    def vxx_to_sentiment(  # noqa: C901
        self,
        vxx_value: float,
        vxx_history: Optional[pd.DataFrame] = None,
        vix_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Convert VXX level to sentiment score using decay-resistant contrarian logic.

        CRITICAL: Uses 30-day rolling percentiles instead of fixed thresholds to handle
        VXX structural decay (~0.5-1% weekly from futures contango). VIX override
        provides sanity checks since VIX doesn't decay.

        Args:
            vxx_value: VXX closing price
            vxx_history: 30-day VXX history for percentile calculation (optional)
            vix_value: VIX value for absolute level override (optional)

        Returns:
            Dict with sentiment score, confidence, and interpretation

        Example:
            {
                "sentiment_score": 0.6,
                "confidence": 0.9,
                "interpretation": "high_fear_buy",
                "reasoning": "VXX at 75th percentile + VIX override - Buy opportunity"
            }
        """
        try:
            # PRIMARY: Use 30-day rolling percentiles for year-over-year adaptability
            if vxx_history is not None and not vxx_history.empty:
                vxx_closes = vxx_history["close"].dropna()
                if len(vxx_closes) >= 10:  # Need minimum data for percentiles
                    from scipy import stats

                    percentile = stats.percentileofscore(vxx_closes, vxx_value)

                    # CONTRARIAN percentile logic: High VXX percentile = High fear = BUY
                    if percentile > 90:
                        sentiment_score = 0.8
                        interpretation = "extreme_fear_buy"
                        reasoning = f"VXX at ${vxx_value:.2f} (90th+ percentile) - Extreme relative fear, CONTRARIAN BUY"
                        confidence = 0.95
                    elif percentile > 75:
                        sentiment_score = 0.6
                        interpretation = "high_fear_buy"
                        reasoning = f"VXX at ${vxx_value:.2f} (75th+ percentile) - High relative fear, CONTRARIAN BUY"
                        confidence = 0.9
                    elif percentile > 60:
                        sentiment_score = 0.3
                        interpretation = "moderate_fear_buy"
                        reasoning = f"VXX at ${vxx_value:.2f} ({percentile:.0f}th percentile) - Moderately elevated fear, mild BUY"
                        confidence = 0.8
                    elif percentile > 40:
                        sentiment_score = 0.0
                        interpretation = "neutral_conditions"
                        reasoning = f"VXX at ${vxx_value:.2f} ({percentile:.0f}th percentile) - True neutral zone"
                        confidence = 0.7
                    elif percentile > 25:
                        sentiment_score = -0.2
                        interpretation = "below_average_caution"
                        reasoning = f"VXX at ${vxx_value:.2f} ({percentile:.0f}th percentile) - Below average fear, mild caution"
                        confidence = 0.7
                    elif percentile > 10:
                        sentiment_score = -0.3
                        interpretation = "low_fear_sell"
                        reasoning = f"VXX at ${vxx_value:.2f} ({percentile:.0f}th percentile) - Low relative fear, CONTRARIAN SELL"
                        confidence = 0.8
                    else:
                        sentiment_score = -0.6
                        interpretation = "extreme_complacency_sell"
                        reasoning = f"VXX at ${vxx_value:.2f} (bottom 10%) - Extreme relative complacency, CONTRARIAN STRONG SELL"
                        confidence = 0.9
                else:
                    # Fallback to fixed thresholds if insufficient percentile data
                    return self._fallback_fixed_thresholds(vxx_value)
            else:
                # Fallback to fixed thresholds if no history available
                return self._fallback_fixed_thresholds(vxx_value)

            # VIX ABSOLUTE LEVEL OVERRIDE (VIX doesn't decay, use as ground truth)
            if vix_value is not None:
                if vix_value > 30:
                    # Force CONTRARIAN BUY on true panic (VIX > 30 = extreme fear = BUY opportunity)
                    sentiment_score = max(sentiment_score, 0.6)
                    reasoning += f" | VIX override: {vix_value:.1f} extreme fear = CONTRARIAN BUY"
                elif vix_value < 12:
                    # Force CONTRARIAN SELL on extreme complacency (VIX < 12 = low fear = SELL signal)
                    sentiment_score = min(sentiment_score, -0.6)
                    reasoning += (
                        f" | VIX override: {vix_value:.1f} extreme complacency = CONTRARIAN SELL"
                    )
                elif 18 <= vix_value <= 25:
                    # Wall of worry zone - sustained moderate fear is BULLISH (2024-specific condition)
                    if 40 <= percentile <= 70:  # Elevated but not spiking
                        sentiment_score = max(sentiment_score, 0.3)
                        reasoning += (
                            f" | Wall of worry: VIX {vix_value:.1f} sustained elevation = BULLISH"
                        )

            return {
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "interpretation": interpretation,
                "reasoning": reasoning,
                "vxx_value": vxx_value,
                "method": "percentile_analysis" if vxx_history is not None else "fixed_thresholds",
            }

        except Exception as e:
            logger.error(f"Error converting VXX {vxx_value} to sentiment: {str(e)}")
            return {
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "interpretation": "error",
                "reasoning": f"Error processing VXX value: {str(e)}",
                "vxx_value": vxx_value,
            }

    def _fallback_fixed_thresholds(self, vxx_value: float) -> Dict[str, Any]:
        """Fallback to original contrarian fixed thresholds when no history available."""
        try:
            # Apply CONTRARIAN VXX logic: "Buy Fear, Sell Greed" (Fixed thresholds)
            if vxx_value > VXX_THRESHOLDS["extreme_fear"]:
                sentiment_score = 0.8
                interpretation = "extreme_fear_buy"
                reasoning = (
                    f"VXX at ${vxx_value:.2f} signals extreme market fear - STRONG BUY opportunity"
                )
                confidence = 0.95
            elif vxx_value > VXX_THRESHOLDS["high_fear"]:
                sentiment_score = 0.6
                interpretation = "high_fear_buy"
                reasoning = f"VXX at ${vxx_value:.2f} signals high market fear - Buy opportunity"
                confidence = 0.9
            elif vxx_value > VXX_THRESHOLDS["moderate_fear"]:
                sentiment_score = 0.3
                interpretation = "moderate_fear_bullish"
                reasoning = f"VXX at ${vxx_value:.2f} shows moderate concern - Mildly bullish"
                confidence = 0.8
            elif vxx_value > VXX_THRESHOLDS["low_fear"]:
                sentiment_score = 0.1
                interpretation = "normal_conditions"
                reasoning = f"VXX at ${vxx_value:.2f} indicates normal market conditions"
                confidence = 0.7
            else:
                sentiment_score = -0.3
                interpretation = "complacency_caution"
                reasoning = f"VXX at ${vxx_value:.2f} shows market complacency - Exercise caution"
                confidence = 0.8

            return {
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "interpretation": interpretation,
                "reasoning": reasoning,
                "vxx_value": vxx_value,
                "thresholds_used": VXX_THRESHOLDS,
                "method": "fixed_thresholds_fallback",
            }
        except Exception as e:
            logger.error(f"Error in fallback VXX sentiment: {str(e)}")
            return {
                "sentiment_score": 0.0,
                "confidence": 0.0,
                "interpretation": "error",
                "reasoning": f"Error in fallback processing: {str(e)}",
                "vxx_value": vxx_value,
            }

    def get_vxx_sentiment(
        self, date: str, lookback_days: int = 5, include_vix: bool = True
    ) -> Dict[str, Any]:
        """
        Get complete VXX-based sentiment analysis with decay-resistant logic.

        CRITICAL FOR 2025: Uses 30-day rolling percentiles + VIX overrides to handle
        VXX structural decay. Without this, V2 will degrade progressively in 2025
        as old data becomes increasingly distorted by futures contango.

        Args:
            date: Target date in YYYY-MM-DD format
            lookback_days: Days to look back if target date has no data
            include_vix: Whether to include VIX override logic

        Returns:
            Dict with decay-resistant sentiment analysis

        Example:
            {
                "sentiment": 0.6,
                "confidence": 0.9,
                "reasoning": "VXX at 80th percentile - Buy on fear | VIX override confirms",
                "version": "V2",
                "mode": "vxx_decay_resistant",
                "method": "percentile_with_vix_override"
            }
        """
        try:
            # Fetch current VXX data
            vxx_data = self.fetch_vxx_data(date, lookback_days)
            if vxx_data is None:
                return {
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "reasoning": f"No VXX volatility data available for {date}",
                    "version": "V2",
                    "mode": "vxx_decay_resistant",
                    "error": "no_vxx_data",
                }

            # Fetch 60-day VXX history for percentile analysis (decay-resistant)
            vxx_history = self.fetch_vxx_history(date, history_days=60)

            # Fetch VIX for override logic (optional)
            vix_value = None
            if include_vix:
                try:
                    vix_df = self.market_tool.fetch_stock_data(
                        symbol="^VIX", start_date=date, end_date=date
                    )
                    if vix_df is not None and not vix_df.empty:
                        vix_value = vix_df.iloc[0]["close"]
                        logger.info(f"VIX value for {date}: {vix_value:.2f}")
                except Exception as e:
                    logger.warning(f"Could not fetch VIX for {date}: {e}")

            # Apply decay-resistant sentiment analysis
            sentiment_analysis = self.vxx_to_sentiment(
                vxx_data["vxx_value"], vxx_history=vxx_history, vix_value=vix_value
            )

            # Combine results with decay-resistant metadata
            result = {
                "sentiment": sentiment_analysis["sentiment_score"],
                "confidence": sentiment_analysis["confidence"],
                "reasoning": sentiment_analysis["reasoning"],
                "version": "V2",
                "mode": "vxx_decay_resistant",
                "vxx_data": vxx_data,
                "interpretation": sentiment_analysis["interpretation"],
                "method": sentiment_analysis.get("method", "percentile_analysis"),
                "vix_value": vix_value,
                "history_days": 60 if vxx_history is not None else 0,
            }

            logger.info(
                f"VXX sentiment (decay-resistant) for {date}: {result['sentiment']:.3f} "
                f"(VXX: ${vxx_data['vxx_value']:.2f}, VIX: {vix_value or 'N/A'}, {sentiment_analysis['interpretation']})"
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
                "error": str(e),
            }

    def validate_vxx_thresholds(
        self, test_cases: Optional[Dict[str, float]] = None
    ) -> Dict[str, bool]:
        """
        Validate VXX sentiment thresholds against test cases.

        Args:
            test_cases: Optional dict of {description: vxx_value} for testing

        Returns:
            Dict with validation results
        """
        if test_cases is None:
            # Default test cases based on contrarian analysis
            test_cases = {
                "COVID crash peak (2020-03)": 80.0,  # Should be STRONG BUY (+0.8)
                "High volatility period": 45.0,  # Should be Buy opportunity (+0.6)
                "Moderate concern": 35.0,  # Should be Mild bullish (+0.3)
                "Normal market": 25.0,  # Should be normal (0.1)
                "Low volatility/complacency": 15.0,  # Should be caution (-0.3)
            }

        results = {}
        expected_sentiments = {80.0: 0.8, 45.0: 0.6, 35.0: 0.3, 25.0: 0.1, 15.0: -0.3}

        for description, vxx_value in test_cases.items():
            sentiment_result = self.vxx_to_sentiment(vxx_value)
            expected = expected_sentiments.get(vxx_value, 0.0)

            is_valid = abs(sentiment_result["sentiment_score"] - expected) < 0.01
            results[description] = {
                "valid": is_valid,
                "vxx_value": vxx_value,
                "calculated_sentiment": sentiment_result["sentiment_score"],
                "expected_sentiment": expected,
                "interpretation": sentiment_result["interpretation"],
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
