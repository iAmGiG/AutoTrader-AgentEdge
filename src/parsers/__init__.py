"""
Input parsers for converting user input into structured TradeRequest.

Available parsers:
- LLMParser: Natural language parsing with an LLM tool call (Microsoft Agent Framework,
  #606). AutoGenLLMParser is its former name, kept as an alias.
- RegexParser: Simple pattern matching (future fallback)
- StructuredParser: Direct input from GUI (future)

Issue #406: Consolidated LLM usage to a single integration path.
"""

from .llm_parser import AutoGenLLMParser, LLMParser

__all__ = [
    "AutoGenLLMParser",
    "LLMParser",
]
