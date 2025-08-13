"""
V3 Sentiment Agent: Heuristic Combination
Combines V1 (VADER NLP) and V2 (Market Fear) with adaptive weighting
Pure mechanical combination, no LLM involvement
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime
import re

from src.agents.sentiment_v1 import SentimentV1Agent
from src.agents.sentiment_v2 import SentimentV2Agent

logger = logging.getLogger(__name__)


class SentimentV3Agent:
    """
    V3: Heuristic Combination Sentiment Agent
    
    Combines V1 (news sentiment) and V2 (market fear) using adaptive weights
    Weights adjust based on market conditions and data availability
    """
    
    def __init__(self, name: str = "SentimentV3Agent", memory_system=None):
        self.name = name
        self.logger = logger
        
        # Initialize V1 and V2 agents
        self.v1_agent = SentimentV1Agent()
        self.v2_agent = SentimentV2Agent()
        
    def calculate_adaptive_weights(self, v1_result: Dict, v2_result: Dict) -> tuple:
        """
        Calculate adaptive weights based on confidence and market conditions.
        
        Args:
            v1_result: V1 sentiment analysis result
            v2_result: V2 sentiment analysis result
            
        Returns:
            Tuple of (v1_weight, v2_weight)
        """
        v1_confidence = v1_result.get("confidence", 0)
        v2_confidence = v2_result.get("confidence", 0)
        
        # Base weights on confidence
        if v1_confidence == 0 and v2_confidence == 0:
            # No data from either source
            return 0.5, 0.5
        elif v1_confidence == 0:
            # Only V2 has data
            return 0.0, 1.0
        elif v2_confidence == 0:
            # Only V1 has data
            return 1.0, 0.0
        else:
            # Both have data - weight by confidence
            total_confidence = v1_confidence + v2_confidence
            v1_weight = v1_confidence / total_confidence
            v2_weight = v2_confidence / total_confidence
            
            # Adjust weights based on market conditions
            vix_level = v2_result.get("vix_current", 20)
            
            if vix_level and vix_level > 30:
                # High volatility - give more weight to market fear
                v2_weight = min(0.7, v2_weight * 1.3)
                v1_weight = 1 - v2_weight
            elif vix_level and vix_level < 15:
                # Low volatility - give more weight to news sentiment
                v1_weight = min(0.7, v1_weight * 1.3)
                v2_weight = 1 - v1_weight
            
            return v1_weight, v2_weight
    
    def combine_sentiments(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Combine V1 and V2 sentiments with adaptive weighting.
        
        Args:
            symbol: Stock ticker symbol
            date: Target date (YYYY-MM-DD)
            
        Returns:
            Dict with combined sentiment analysis
        """
        try:
            # Get V1 sentiment (news-based)
            v1_message = f"{symbol} on {date}"
            v1_response = self.v1_agent.generate_reply(v1_message)
            v1_result = json.loads(v1_response)
            
            # Get V2 sentiment (VIX-based)
            v2_message = f"market fear on {date}"
            v2_response = self.v2_agent.generate_reply(v2_message)
            v2_result = json.loads(v2_response)
            
            # Calculate adaptive weights
            v1_weight, v2_weight = self.calculate_adaptive_weights(v1_result, v2_result)
            
            # Combine sentiments
            v1_sentiment = v1_result.get("sentiment", 0)
            v2_sentiment = v2_result.get("sentiment", 0)
            
            combined_sentiment = (v1_sentiment * v1_weight) + (v2_sentiment * v2_weight)
            
            # Combine confidence scores
            v1_confidence = v1_result.get("confidence", 0)
            v2_confidence = v2_result.get("confidence", 0)
            combined_confidence = (v1_confidence * v1_weight) + (v2_confidence * v2_weight)
            
            # Generate reasoning
            reasoning_parts = []
            if v1_weight > 0:
                reasoning_parts.append(
                    f"News sentiment ({v1_weight:.0%} weight): {v1_sentiment:.3f}"
                )
            if v2_weight > 0:
                vix_val = v2_result.get("vix_current", "N/A")
                reasoning_parts.append(
                    f"Market fear/VIX ({v2_weight:.0%} weight): {v2_sentiment:.3f} (VIX: {vix_val})"
                )
            
            reasoning = f"Heuristic combination - {' | '.join(reasoning_parts)}"
            
            result = {
                "sentiment": round(combined_sentiment, 4),
                "confidence": round(combined_confidence, 4),
                "reasoning": reasoning,
                "v1_sentiment": round(v1_sentiment, 4),
                "v1_weight": round(v1_weight, 4),
                "v1_confidence": round(v1_confidence, 4),
                "v2_sentiment": round(v2_sentiment, 4),
                "v2_weight": round(v2_weight, 4),
                "v2_confidence": round(v2_confidence, 4),
                "articles_analyzed": v1_result.get("articles_analyzed", 0),
                "vix_current": v2_result.get("vix_current"),
                "mode": "heuristic_combination",
                "version": "V3"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in V3 sentiment combination: {str(e)}")
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "reasoning": f"Error combining sentiments: {str(e)}",
                "mode": "heuristic_combination",
                "version": "V3"
            }
    
    def generate_reply(self, messages, context=None) -> str:
        """
        Generate combined heuristic sentiment response.
        
        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context (not used)
            
        Returns:
            JSON string with combined sentiment analysis
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
        
        # Parse for symbol and date
        symbol_match = re.search(r'\b([A-Z]{2,5})\b', message)
        symbol = symbol_match.group(1) if symbol_match else "SPY"
        
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
        date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"V3 Sentiment: Combining V1 and V2 for {symbol} on {date}")
        
        # Combine sentiments
        result = self.combine_sentiments(symbol, date)
        
        # Log the result
        logger.info(
            f"V3 Result: sentiment={result['sentiment']}, "
            f"V1={result.get('v1_sentiment', 'N/A')} ({result.get('v1_weight', 0):.0%}), "
            f"V2={result.get('v2_sentiment', 'N/A')} ({result.get('v2_weight', 0):.0%})"
        )
        
        return json.dumps(result)