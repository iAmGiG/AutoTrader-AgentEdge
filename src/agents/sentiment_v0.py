"""
V0 Sentiment Agent: Fixed Baseline
Always returns sentiment = 1.0 for pure MACD strategy baseline
Extends BaseAgent for consistent interface but uses no tools or LLM
"""

import json
import logging
from typing import Dict, Any

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class V0SentimentAgent(BaseAgent):
    """
    V0: Fixed Baseline Sentiment Agent
    
    Always returns sentiment = 1.0 (fully bullish/neutral)
    This provides a baseline where MACD signals are never dampened
    No data fetching, no processing, no external dependencies
    """
    
    def __init__(self, name: str = "V0SentimentAgent", memory_system=None):
        # Minimal LLM config for BaseAgent compatibility (won't be used)
        minimal_config = {
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 100
        }
        
        # Initialize BaseAgent with empty tools and minimal config
        super().__init__(
            name=name,
            tools=[],  # No tools for fixed baseline
            memory_system=memory_system,
            llm_config=minimal_config  # Minimal config for compatibility
        )
        
        self.logger = logger
        self.fixed_sentiment = 1.0
    
    def generate_reply(self, messages, context=None) -> str:
        """
        Generate fixed sentiment response.
        
        Args:
            messages: Input messages (ignored for V0)
            context: Optional context (ignored for V0)
            
        Returns:
            JSON string with fixed sentiment = 1.0
        """
        logger.info(f"V0SentimentAgent: Returning fixed baseline sentiment = {self.fixed_sentiment}")
        
        result = {
            "score": self.fixed_sentiment,
            "confidence": 1.0,
            "reasoning": "V0: Fixed baseline - no sentiment filtering",
            "version": "V0",
            "data_sources": []  # No external data sources
        }
        
        return json.dumps(result)
    
    def get_sentiment(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Alternative method for getting sentiment (matches issue #181 interface).
        
        Args:
            symbol: Stock ticker (ignored for V0)
            date: Date string (ignored for V0)
            
        Returns:
            Dict with fixed sentiment values
        """
        return {
            "score": self.fixed_sentiment,
            "confidence": 1.0,
            "reasoning": "V0: Fixed baseline - no sentiment filtering",
            "version": "V0",
            "data_sources": []
        }