"""
Input parsers for converting user input into structured TradeRequest.

Available parsers:
- LLMParser: Natural language parsing using LLM
- RegexParser: Simple pattern matching (future fallback)
- StructuredParser: Direct input from GUI (future)
"""

from .llm_parser import LLMParser

__all__ = [
    "LLMParser",
]
