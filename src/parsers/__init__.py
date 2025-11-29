"""
Input parsers for converting user input into structured TradeRequest.

Available parsers:
- AutoGenLLMParser: Natural language parsing using AutoGen's native LLM client
- RegexParser: Simple pattern matching (future fallback)
- StructuredParser: Direct input from GUI (future)

Issue #406: Consolidated to use AutoGen's native OpenAIChatCompletionClient.
"""

from .autogen_llm_parser import AutoGenLLMParser

__all__ = [
    "AutoGenLLMParser",
]
