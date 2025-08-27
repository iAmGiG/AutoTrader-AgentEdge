"""
V3 Sentiment Agent: Heuristic Combination (OPTIMIZED)
Combines V1 (VADER NLP) and V2 (Market Fear) without unnecessary LLM calls
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.agents.base_agent import BaseAgent
from .sentiment_v1 import SentimentV1Agent
from .sentiment_v2 import SentimentV2Agent

logger = logging.getLogger(__name__)


class SentimentV3Agent(BaseAgent):
    """
    V3: Heuristic Combination Sentiment Agent (OPTIMIZED)

    Key Optimizations:
    - Uses optimized V1 and V2 agents directly
    - No LLM calls for mechanical combination
    - Batch processing for entire periods
    - Adaptive weighting based on confidence
    """

    def __init__(self, name: str = "SentimentV3Agent", memory_system=None):
        # Initialize optimized V1 and V2 agents
        self.v1_agent = SentimentV1Agent()
        self.v2_agent = SentimentV2Agent()
        
        # Batch processing state
        self.batch_sentiments: Dict[str, float] = {}  # {date: sentiment_score}
        self.is_batch_prepared = False
        self.prepared_symbol = None
        self.prepared_period = None

        # Call parent constructor with sentiment tools
        from src.tools.tools import SENTIMENT_TOOLS
        super().__init__(
            name=name,
            tools=SENTIMENT_TOOLS,
            memory_system=memory_system
        )

        self.logger = logger

    def calculate_adaptive_weights(self, v1_sentiment: float, v2_sentiment: float) -> tuple:
        """
        Calculate adaptive weights based on market conditions.
        
        During high volatility (strong V2 signal), weight V2 more heavily.
        During normal conditions, balanced weighting.
        
        Args:
            v1_sentiment: News-based sentiment from V1
            v2_sentiment: VXX-based sentiment from V2
            
        Returns:
            Tuple of (v1_weight, v2_weight)
        """
        # If V2 shows extreme fear or greed, weight it more
        v2_abs = abs(v2_sentiment)
        
        if v2_abs > 0.6:  # Strong VXX signal
            # High volatility - V2 gets more weight
            v1_weight = 0.3
            v2_weight = 0.7
        elif v2_abs > 0.3:  # Moderate VXX signal
            # Moderate volatility - balanced weights
            v1_weight = 0.5
            v2_weight = 0.5
        else:  # Weak VXX signal
            # Low volatility - V1 gets more weight
            v1_weight = 0.7
            v2_weight = 0.3
            
        return v1_weight, v2_weight

    def prepare_period_data(self, symbol: str, start_date: str, end_date: str) -> bool:
        """
        Batch prepare combined sentiment data for entire period WITHOUT LLM calls.
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            start_date: Period start date in YYYY-MM-DD format
            end_date: Period end date in YYYY-MM-DD format
            
        Returns:
            bool: True if preparation successful
        """
        try:
            self.logger.info(f"V3 Optimized: Batch preparing combined sentiment from {start_date} to {end_date}")
            
            # Clear previous batch data
            self.batch_sentiments.clear()
            self.is_batch_prepared = False
            
            # Prepare V1 and V2 data in parallel (no LLM calls)
            v1_success = self.v1_agent.prepare_period_data(symbol, start_date, end_date)
            v2_success = self.v2_agent.prepare_period_data(symbol, start_date, end_date)
            
            if not v1_success or not v2_success:
                self.logger.warning("V3 Optimized: Failed to prepare V1 or V2 data")
                return False
            
            # Combine sentiments using adaptive weighting
            all_dates = set(self.v1_agent.batch_sentiments.keys()) | set(self.v2_agent.batch_sentiments.keys())
            
            for date_str in all_dates:
                v1_sentiment = self.v1_agent.batch_sentiments.get(date_str, 0.0)
                v2_sentiment = self.v2_agent.batch_sentiments.get(date_str, 0.0)
                
                # Calculate adaptive weights
                v1_weight, v2_weight = self.calculate_adaptive_weights(v1_sentiment, v2_sentiment)
                
                # Combine sentiments
                combined_sentiment = (v1_sentiment * v1_weight) + (v2_sentiment * v2_weight)
                
                self.batch_sentiments[date_str] = combined_sentiment
            
            self.logger.info(
                f"V3 Optimized: Prepared {len(self.batch_sentiments)} combined sentiments"
            )
            
            self.is_batch_prepared = True
            self.prepared_symbol = symbol
            self.prepared_period = (start_date, end_date)
            
            return True
            
        except Exception as e:
            self.logger.error(f"V3 Optimized: Batch preparation failed: {e}")
            return False

    def generate_reply(self, messages, context=None) -> str:
        """
        Generate V3 sentiment response using OPTIMIZED approach.
        
        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context
            
        Returns:
            JSON string with V3 sentiment analysis
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

        # Extract date from message
        import re
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', message)
        date = date_match.group(0) if date_match else datetime.now().strftime("%Y-%m-%d")
        
        # Extract symbol from message
        symbol_match = re.search(r'\b([A-Z]{2,5})\b', message)
        symbol = symbol_match.group(1) if symbol_match else "AAPL"

        # OPTIMIZATION: Use batch prepared data if available
        if self.is_batch_prepared and date in self.batch_sentiments:
            sentiment = self.batch_sentiments[date]
            v1_sentiment = self.v1_agent.batch_sentiments.get(date, 0.0)
            v2_sentiment = self.v2_agent.batch_sentiments.get(date, 0.0)
            
            self.logger.info(f"V3 Optimized: Using batch prepared combined sentiment for {date}: {sentiment:.3f}")
            
            return json.dumps({
                "sentiment": round(sentiment, 4),
                "confidence": 0.75,
                "version": "V3",
                "mode": "batch_optimized",
                "reasoning": f"Combined V1 (news: {v1_sentiment:.2f}) + V2 (VXX: {v2_sentiment:.2f})",
                "components": {
                    "v1_sentiment": round(v1_sentiment, 4),
                    "v2_sentiment": round(v2_sentiment, 4)
                },
                "date": date
            })
        
        # OPTIMIZATION: Try direct combination without LLM
        try:
            self.logger.info(f"V3 Optimized: Direct combining V1+V2 for {symbol} on {date}")
            
            # Get V1 and V2 sentiments directly (they will use their optimized paths)
            v1_response = self.v1_agent.generate_reply(message, context)
            v2_response = self.v2_agent.generate_reply(message, context)
            
            v1_data = json.loads(v1_response) if isinstance(v1_response, str) else v1_response
            v2_data = json.loads(v2_response) if isinstance(v2_response, str) else v2_response
            
            v1_sentiment = v1_data.get('sentiment', 0.0)
            v2_sentiment = v2_data.get('sentiment', 0.0)
            
            # Calculate adaptive weights and combine
            v1_weight, v2_weight = self.calculate_adaptive_weights(v1_sentiment, v2_sentiment)
            combined_sentiment = (v1_sentiment * v1_weight) + (v2_sentiment * v2_weight)
            
            return json.dumps({
                "sentiment": round(combined_sentiment, 4),
                "confidence": 0.75,
                "version": "V3",
                "mode": "direct_optimized",
                "reasoning": f"Combined V1 ({v1_weight:.1f} weight) + V2 ({v2_weight:.1f} weight)",
                "components": {
                    "v1_sentiment": round(v1_sentiment, 4),
                    "v2_sentiment": round(v2_sentiment, 4),
                    "v1_weight": v1_weight,
                    "v2_weight": v2_weight
                },
                "date": date
            })
            
        except Exception as e:
            self.logger.warning(f"V3 Optimized: Direct combination failed, falling back to LLM: {e}")
            
            # Fall back to original LLM-based approach if direct access fails
            return super().generate_reply(messages, context)

    def get_sentiment(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Alternative method for getting sentiment.
        
        Args:
            symbol: Stock ticker
            date: Date string
            
        Returns:
            Dict with sentiment values
        """
        # Use batch prepared data if available
        if self.is_batch_prepared and date in self.batch_sentiments:
            return {
                "score": self.batch_sentiments[date],
                "confidence": 0.75,
                "reasoning": "V3 Optimized: Batch prepared combined analysis",
                "version": "V3",
                "data_sources": ["google_news", "vxx_volatility"]
            }
        
        # Otherwise generate reply
        response = self.generate_reply(f"{symbol} on {date}")
        if isinstance(response, str):
            return json.loads(response)
        return response