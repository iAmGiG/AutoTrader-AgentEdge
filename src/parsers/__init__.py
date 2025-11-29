"""
Input parsers for converting user input into structured TradeRequest.

Available parsers:
- AutoGenLLMParser: Natural language parsing using AutoGen's native LLM client (recommended)
- LLMParser: Legacy parser using custom OpenAIService (deprecated, use AutoGenLLMParser)
- RegexParser: Simple pattern matching (future fallback)
- StructuredParser: Direct input from GUI (future)
"""

from .autogen_llm_parser import AutoGenLLMParser
from .llm_parser import LLMParser

__all__ = [
    "AutoGenLLMParser",  # Recommended
    "LLMParser",  # Deprecated - kept for backward compatibility
]
