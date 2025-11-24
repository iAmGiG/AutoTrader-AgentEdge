"""
LLM Service abstraction.

Provides a unified interface for calling different LLM providers (OpenAI, Anthropic, local).
This allows swapping providers via configuration without code changes.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional


class LLMProvider(Enum):
    """Supported LLM providers"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class LLMService(ABC):
    """
    Abstract LLM interface.

    Implementations:
    - OpenAIService: gpt-4o-mini, o3-mini
    - AnthropicService: Claude Sonnet, Haiku
    - LocalLLMService: Ollama, LM Studio
    """

    @abstractmethod
    async def call_tool(
        self, prompt: str, tools: List[Dict[str, Any]], temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Call LLM with tool/function calling capability.

        Used for structured parsing (e.g., extracting ticker, quantity from NL input).

        Args:
            prompt: User prompt
            tools: List of tool definitions (OpenAI function calling format)
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            Dict with tool call results

        Example:
            tools = [{
                "name": "parse_trade_request",
                "description": "Parse user trade request",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "action": {"type": "string"},
                        "quantity": {"type": "integer"},
                    }
                }
            }]
            result = await llm.call_tool("buy 50 SPY", tools)
        """
        pass

    @abstractmethod
    async def reason(
        self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.7
    ) -> str:
        """
        Call LLM for reasoning/generation.

        Used for generating suggestions, explanations, etc.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        pass

    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        """LLM provider type"""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name being used"""
        pass
