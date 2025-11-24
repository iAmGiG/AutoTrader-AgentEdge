"""
InputParser interface.

Defines the contract for parsing user input into structured TradeRequest objects.
Implementations can use LLMs, regex, or structured input (GUI).
"""

from abc import ABC, abstractmethod
from typing import Optional

from ..models import TradeRequest


class InputParser(ABC):
    """
    Abstract interface for parsing user input into trade requests.

    Implementations:
    - LLMParser: Uses LLM (OpenAI, Anthropic) for natural language parsing
    - RegexParser: Simple pattern matching (fallback)
    - StructuredParser: Direct input from GUI (no parsing needed)
    """

    @abstractmethod
    async def parse(self, user_input: str, user_id: Optional[str] = None) -> TradeRequest:
        """
        Parse user input into structured TradeRequest.

        Args:
            user_input: Raw user input (e.g., "is SPY at 600 good?")
            user_id: Optional user ID for context

        Returns:
            TradeRequest with extracted ticker, action, quantity, price

        Raises:
            ValueError: If input cannot be parsed
        """
        pass

    @abstractmethod
    async def validate(self, request: TradeRequest) -> bool:
        """
        Validate a parsed request.

        Args:
            request: Parsed TradeRequest

        Returns:
            True if valid, False otherwise

        Examples of validation:
        - Is ticker a valid symbol?
        - Is quantity positive?
        - Is price reasonable?
        """
        pass
