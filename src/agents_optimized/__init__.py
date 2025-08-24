"""
Optimized Agents for RH2MAS
These agents reduce unnecessary LLM calls through direct tool access and batch processing
"""

from .sentiment_v0 import V0SentimentAgent
from .sentiment_v1 import OptimizedSentimentV1Agent
from .sentiment_v2 import OptimizedSentimentV2Agent
from .sentiment_v3 import OptimizedSentimentV3Agent
from .sentiment_v4 import OptimizedSentimentV4Agent

__all__ = [
    'V0SentimentAgent',
    'OptimizedSentimentV1Agent',
    'OptimizedSentimentV2Agent', 
    'OptimizedSentimentV3Agent',
    'OptimizedSentimentV4Agent'
]