"""
V2 Sentiment Agent: Market Fear Based (VXX Volatility) - OPTIMIZED
Direct VXX tool access bypassing LLM when data is cached
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from src.agents.base_agent import BaseAgent
from src.tools.data_sources.market.vxx_volatility_tool import VXXVolatilityTool

logger = logging.getLogger(__name__)


class SentimentV2Agent(BaseAgent):
    """
    V2: Market Fear-based Sentiment Agent (OPTIMIZED)

    Key Optimizations:
    - Direct VXX tool access bypassing LLM 
    - Leverages AlphaVantage/UnifiedCache for market data
    - Batch processing for entire periods
    - Falls back to LLM only when necessary
    """

    def __init__(self, name: str = "SentimentV2Agent", memory_system=None):
        # Direct tool access for optimization
        self.vxx_tool = VXXVolatilityTool()
        
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

    def prepare_period_data(self, symbol: str, start_date: str, end_date: str) -> bool:
        """
        Batch prepare VXX sentiment data for entire period WITHOUT LLM calls.
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL') - used for context
            start_date: Period start date in YYYY-MM-DD format
            end_date: Period end date in YYYY-MM-DD format
            
        Returns:
            bool: True if preparation successful
        """
        try:
            self.logger.info(f"V2 Optimized: Batch preparing VXX data from {start_date} to {end_date}")
            
            # Clear previous batch data
            self.batch_sentiments.clear()
            self.is_batch_prepared = False
            
            # Generate trading days
            trading_days = self._generate_trading_days(start_date, end_date)
            
            # Process each day with direct VXX tool access
            for date_str in trading_days:
                try:
                    # Direct tool call WITHOUT LLM
                    vxx_result = self.vxx_tool.fetch_vxx_data(date_str)
                    
                    if vxx_result:
                        # Convert VXX to sentiment using same logic as original V2
                        vxx_sentiment_result = self.vxx_tool.vxx_to_sentiment(vxx_result['vxx_value'])
                        sentiment = vxx_sentiment_result.get('sentiment_score', 0.0)
                    else:
                        sentiment = 0.0  # Neutral if no data
                        
                    self.batch_sentiments[date_str] = sentiment
                    
                except Exception as e:
                    self.logger.debug(f"No VXX data for {date_str}: {e}")
                    self.batch_sentiments[date_str] = 0.0
            
            self.logger.info(
                f"V2 Optimized: Prepared {len(self.batch_sentiments)} daily VXX sentiments"
            )
            
            self.is_batch_prepared = True
            self.prepared_symbol = symbol
            self.prepared_period = (start_date, end_date)
            
            return True
            
        except Exception as e:
            self.logger.error(f"V2 Optimized: Batch preparation failed: {e}")
            return False

    def _generate_trading_days(self, start_date: str, end_date: str) -> list:
        """Generate list of trading days between start and end dates."""
        trading_days = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current <= end:
            # Skip weekends
            if current.weekday() < 5:
                trading_days.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
            
        return trading_days

    def generate_reply(self, messages, context=None) -> str:
        """
        Generate V2 sentiment response using OPTIMIZED approach.
        
        Args:
            messages: Input messages (expects symbol and date)
            context: Optional context
            
        Returns:
            JSON string with V2 sentiment analysis
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
            self.logger.info(f"V2 Optimized: Using batch prepared VXX sentiment for {date}: {sentiment:.3f}")
            
            return json.dumps({
                "sentiment": round(sentiment, 4),
                "confidence": 0.8,
                "version": "V2",
                "mode": "batch_optimized",
                "reasoning": f"VXX volatility-based market fear sentiment",
                "date": date
            })
        
        # OPTIMIZATION: Try direct tool access first
        try:
            self.logger.info(f"V2 Optimized: Direct fetching VXX for {date}")
            
            # Direct tool call WITHOUT LLM
            vxx_result = self.vxx_tool.fetch_vxx_data(date)
            
            if vxx_result:
                vxx_sentiment_result = self.vxx_tool.vxx_to_sentiment(vxx_result['vxx_value'])
                sentiment = vxx_sentiment_result.get('sentiment_score', 0.0)
                
                return json.dumps({
                    "sentiment": round(sentiment, 4),
                    "confidence": 0.8,
                    "version": "V2",
                    "mode": "direct_optimized",
                    "reasoning": f"VXX={vxx_result['vxx_value']:.2f} on {vxx_result['date_used']}",
                    "date": date
                })
            else:
                # No VXX data available
                return json.dumps({
                    "sentiment": 0.0,
                    "confidence": 0.0,
                    "version": "V2",
                    "mode": "no_data",
                    "reasoning": "No VXX data available",
                    "date": date
                })
            
        except Exception as e:
            self.logger.warning(f"V2 Optimized: Direct access failed, falling back to LLM: {e}")
            
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
                "confidence": 0.8,
                "reasoning": "V2 Optimized: Batch prepared VXX analysis",
                "version": "V2",
                "data_sources": ["vxx_volatility"]
            }
        
        # Otherwise generate reply
        response = self.generate_reply(f"{symbol} on {date}")
        if isinstance(response, str):
            return json.loads(response)
        return response