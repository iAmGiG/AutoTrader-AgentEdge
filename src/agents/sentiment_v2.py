"""
V2 Sentiment Agent: Market Fear Based (VIX/VXX)
Uses volatility indices to gauge market sentiment
Pure mechanical calculation, no LLM involvement
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
import re
import pandas as pd

from src.tools.tools import fetch_market_data

logger = logging.getLogger(__name__)


class SentimentV2Agent:
    """
    V2: Market Fear-based Sentiment Agent
    
    Uses VIX (volatility index) to determine market sentiment
    High VIX = High fear = Bearish sentiment
    Low VIX = Low fear = Bullish sentiment
    """
    
    def __init__(self, name: str = "SentimentV2Agent", memory_system=None):
        self.name = name
        self.logger = logger
        
        # VIX thresholds for sentiment mapping
        self.vix_thresholds = {
            "extreme_fear": 35,     # > 35 = extreme fear
            "high_fear": 25,        # 25-35 = high fear  
            "moderate": 20,         # 20-25 = moderate fear
            "low_fear": 15,         # 15-20 = low fear
            "complacent": 10        # < 15 = complacency
        }
        
    def calculate_vix_sentiment(self, vix_value: float, vix_change: float) -> Dict[str, Any]:
        """
        Convert VIX level and change to sentiment score.
        
        Args:
            vix_value: Current VIX value
            vix_change: Change in VIX from previous day
            
        Returns:
            Dict with sentiment score and reasoning
        """
        # Map VIX to sentiment (-1 to 1)
        # High VIX = negative sentiment, Low VIX = positive sentiment
        
        if vix_value >= self.vix_thresholds["extreme_fear"]:
            base_sentiment = -0.9
            fear_level = "extreme fear"
        elif vix_value >= self.vix_thresholds["high_fear"]:
            base_sentiment = -0.6
            fear_level = "high fear"
        elif vix_value >= self.vix_thresholds["moderate"]:
            base_sentiment = -0.3
            fear_level = "moderate fear"
        elif vix_value >= self.vix_thresholds["low_fear"]:
            base_sentiment = 0.1
            fear_level = "low fear"
        else:
            base_sentiment = 0.5
            fear_level = "market complacency"
        
        # Adjust for VIX momentum
        if vix_change > 5:  # Sharp increase in fear
            momentum_adj = -0.2
            momentum_desc = "sharply increasing"
        elif vix_change > 2:
            momentum_adj = -0.1
            momentum_desc = "increasing"
        elif vix_change < -5:  # Sharp decrease in fear
            momentum_adj = 0.2
            momentum_desc = "sharply decreasing"
        elif vix_change < -2:
            momentum_adj = 0.1
            momentum_desc = "decreasing"
        else:
            momentum_adj = 0
            momentum_desc = "stable"
        
        # Final sentiment
        final_sentiment = max(-1, min(1, base_sentiment + momentum_adj))
        
        # Confidence based on VIX clarity
        if vix_value > 30 or vix_value < 12:
            confidence = 0.8  # Clear signal
        elif vix_value > 25 or vix_value < 15:
            confidence = 0.6  # Moderate signal
        else:
            confidence = 0.4  # Unclear signal
        
        reasoning = (
            f"VIX at {vix_value:.2f} indicates {fear_level}, "
            f"{momentum_desc} (change: {vix_change:+.2f})"
        )
        
        return {
            "sentiment": final_sentiment,
            "confidence": confidence,
            "reasoning": reasoning,
            "vix_level": vix_value,
            "vix_change": vix_change,
            "fear_level": fear_level
        }
    
    def fetch_and_analyze_vix(self, date: str) -> Dict[str, Any]:
        """
        Fetch VIX data and calculate fear-based sentiment.
        
        Args:
            date: Target date (YYYY-MM-DD)
            
        Returns:
            Dict with VIX-based sentiment analysis
        """
        try:
            # Fetch VIX data for past week
            end_date = pd.to_datetime(date)
            start_date = end_date - timedelta(days=10)
            
            vix_data = fetch_market_data(
                symbol="^VIX",  # Try with caret prefix
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d")
            )
            
            # If that fails, try without caret
            if vix_data is None or vix_data.empty:
                vix_data = fetch_market_data(
                    symbol="VIX",
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d")
                )
            
            if vix_data is None or vix_data.empty:
                logger.warning("No VIX data available, using default neutral sentiment")
                return {
                    "sentiment": 0.0,
                    "confidence": 0.2,
                    "reasoning": "VIX data unavailable, defaulting to neutral",
                    "mode": "market_fear",
                    "version": "V2"
                }
            
            # Ensure we have Close column
            if 'Close' not in vix_data.columns and 'close' in vix_data.columns:
                vix_data['Close'] = vix_data['close']
            
            # Get current and previous VIX values
            current_vix = float(vix_data['Close'].iloc[-1])
            prev_vix = float(vix_data['Close'].iloc[-2]) if len(vix_data) > 1 else current_vix
            vix_change = current_vix - prev_vix
            
            # Calculate sentiment based on VIX
            analysis = self.calculate_vix_sentiment(current_vix, vix_change)
            
            result = {
                "sentiment": round(analysis["sentiment"], 4),
                "confidence": round(analysis["confidence"], 4),
                "reasoning": analysis["reasoning"],
                "vix_current": round(current_vix, 2),
                "vix_previous": round(prev_vix, 2),
                "vix_change": round(vix_change, 2),
                "fear_level": analysis["fear_level"],
                "mode": "market_fear",
                "version": "V2"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in V2 sentiment analysis: {str(e)}")
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error fetching VIX data: {str(e)}",
                "mode": "market_fear",
                "version": "V2"
            }
    
    def generate_reply(self, messages, context=None) -> str:
        """
        Generate VIX-based sentiment response.
        
        Args:
            messages: Input messages (expects date)
            context: Optional context (not used)
            
        Returns:
            JSON string with VIX-based sentiment analysis
        """
        # Extract message content
        if isinstance(messages, str):
            message = messages
        elif isinstance(messages, list) and messages:
            message = messages[-1].get("content", "") if isinstance(messages[-1], dict) else str(messages[-1])
        elif isinstance(messages, dict):
            message = messages.get("content", "")
        else:
            message = ""
        
        # Parse for date (symbol not needed for VIX)
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
        date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"V2 Sentiment: Analyzing market fear for {date} using VIX")
        
        # Fetch and analyze VIX
        result = self.fetch_and_analyze_vix(date)
        
        # Log the result
        logger.info(f"V2 Result: sentiment={result['sentiment']}, VIX={result.get('vix_current', 'N/A')}")
        
        return json.dumps(result)