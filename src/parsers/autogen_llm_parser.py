"""
AutoGen-based natural language parser.

Uses AutoGen's native LLM client (OpenAIChatCompletionClient) and FunctionTool
instead of a custom OpenAI wrapper. This consolidates LLM usage to a single
integration path.

Issue #406: Consolidate LLM services
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional

from autogen_core.models import UserMessage
from autogen_core.tools import FunctionTool
from autogen_ext.models.openai import OpenAIChatCompletionClient
from core.interfaces import InputParser
from core.models import AssetType, TradeRequest

from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

# Load configuration (shared with base_agent.py pattern)
config_loader = ConfigLoader()

# Get API key and model from environment or config
_api_key = os.getenv("OPEN_AI_KEY", config_loader.get("OPEN_AI_KEY"))
_tool_model = os.getenv(
    "OPENAI_TOOL_MODEL",
    config_loader.get("OPENAI_TOOL_MODEL", "gpt-4o-mini"),
)


class RequestType(str, Enum):
    """Type of user request."""

    TRADE = "trade"
    STATUS_QUERY = "status_query"


class ActionType(str, Enum):
    """User's intended action."""

    REVIEW = "review"
    BUY = "buy"
    SELL = "sell"


@dataclass
class ParsedTradeRequest:
    """
    Structured output from parsing user input.

    This dataclass defines the schema that the LLM will extract.
    AutoGen's FunctionTool generates the JSON schema from these type hints.
    """

    request_type: Literal["trade", "status_query"]
    ticker: str
    action: Literal["review", "buy", "sell"]
    quantity: Optional[int] = None
    price: Optional[float] = None
    asset_type: Literal["stock", "option"] = "stock"


def _parse_trade_request(
    request_type: Literal["trade", "status_query"],
    ticker: str,
    action: Literal["review", "buy", "sell"],
    quantity: Optional[int] = None,
    price: Optional[float] = None,
    asset_type: Literal["stock", "option"] = "stock",
) -> dict:
    """
    Parse user's trade request into structured format.

    This function is wrapped by AutoGen's FunctionTool to create a tool
    that the LLM can call. The type hints define the JSON schema.

    Args:
        request_type: "trade" for buy/sell/analyze, "status_query" for account status
        ticker: Stock ticker symbol (e.g., SPY, AAPL). Empty for status queries.
        action: User's intent - review (analyze), buy, or sell
        quantity: Number of shares (optional)
        price: Entry price mentioned (optional)
        asset_type: "stock" (default) or "option"

    Returns:
        Parsed request as dictionary
    """
    return {
        "request_type": request_type,
        "ticker": ticker.upper() if ticker else "",
        "action": action,
        "quantity": quantity,
        "price": price,
        "asset_type": asset_type,
    }


# Create the AutoGen FunctionTool - schema auto-generated from type hints
PARSE_TOOL = FunctionTool(
    func=_parse_trade_request,
    name="parse_trade_request",
    description="Parse user's trade request into structured format",
)


class AutoGenLLMParser(InputParser):
    """
    Parse natural language input using AutoGen's native LLM client.

    This replaces the custom OpenAIService with AutoGen's OpenAIChatCompletionClient,
    consolidating LLM usage to a single integration path.

    Examples:
    - "is SPY at 600 good?" -> TradeRequest(ticker="SPY", action="review", price=600)
    - "buy 50 AAPL" -> TradeRequest(ticker="AAPL", action="buy", quantity=50)
    - "any open orders?" -> TradeRequest(request_type="status_query")
    """

    def __init__(
        self,
        model_client: Optional[OpenAIChatCompletionClient] = None,
        model: str = None,
        api_key: str = None,
    ):
        """
        Initialize with AutoGen's OpenAI client.

        Args:
            model_client: Pre-configured client (optional)
            model: Model name (default: gpt-4o-mini from config)
            api_key: API key (default: from config/env)
        """
        if model_client is not None:
            self.client = model_client
        else:
            # Create client using shared config pattern from base_agent.py
            key = api_key or _api_key
            if not key:
                raise ValueError(
                    "OpenAI API key not found. Set OPEN_AI_KEY environment variable "
                    "or update config.json"
                )

            self.client = OpenAIChatCompletionClient(
                model=model or _tool_model,
                api_key=key,
                temperature=0.0,  # Deterministic for parsing
                max_tokens=1024,
            )

        self._tool = PARSE_TOOL
        logger.info(f"AutoGenLLMParser initialized with model: {model or _tool_model}")

    async def parse(self, user_input: str, user_id: Optional[str] = None) -> TradeRequest:
        """
        Parse user input into TradeRequest using AutoGen's LLM client.

        Args:
            user_input: Raw user input
            user_id: Optional user ID (for future personalization)

        Returns:
            Parsed TradeRequest

        Raises:
            ValueError: If input cannot be parsed
        """
        # Auto-correct obvious errors first
        corrected_input = self._autocorrect(user_input)

        # Build prompt
        prompt = self._build_prompt(corrected_input)

        try:
            # Call LLM with tool
            messages = [UserMessage(content=prompt, source="user")]
            response = await self.client.create(
                messages=messages,
                tools=[self._tool],
            )

            # Extract tool call from response
            if not hasattr(response, "content") or not isinstance(response.content, list):
                raise ValueError(f"Unexpected response format: {response}")

            # Find the tool call in the response
            tool_call = None
            for item in response.content:
                if hasattr(item, "name") and item.name == "parse_trade_request":
                    tool_call = item
                    break

            if tool_call is None:
                raise ValueError(f"No tool call in response for: {user_input}")

            # Parse arguments (already a dict from AutoGen)
            args = tool_call.arguments
            if isinstance(args, str):
                args = json.loads(args)

            # Create TradeRequest
            request = TradeRequest(
                ticker=args.get("ticker", "").upper(),
                action=args.get("action", "review"),
                request_type=args.get("request_type", "trade"),
                quantity=args.get("quantity"),
                price=args.get("price"),
                asset_type=AssetType(args.get("asset_type", "stock")),
                raw_input=user_input,
            )

            logger.info(
                f"Parsed: '{user_input}' -> {request.action} {request.ticker}"
                + (f" qty={request.quantity}" if request.quantity else "")
                + (f" @{request.price}" if request.price else "")
            )

            return request

        except Exception as e:
            # Catch specific OpenAI API auth errors
            error_str = str(e).lower()
            if "401" in error_str or "authentication" in error_str or "api key" in error_str:
                logger.error("OpenAI API authentication error", exc_info=True)
                raise ValueError("Configuration error") from e

            # Generic parse failure - simple message
            logger.debug(f"Parse error for input '{user_input}': {e}", exc_info=True)
            raise ValueError("Could not parse input") from e

    async def validate(self, request: TradeRequest) -> bool:
        """
        Validate parsed request.

        Args:
            request: Parsed TradeRequest

        Returns:
            True if valid
        """
        # Skip validation for status queries
        if request.request_type == "status_query":
            return True

        # Ticker validation (1-5 uppercase letters)
        if request.ticker and not re.match(r"^[A-Z]{1,5}$", request.ticker):
            logger.debug(f"Invalid ticker format: {request.ticker}")
            return False

        # Quantity validation
        if request.quantity is not None and request.quantity <= 0:
            logger.warning(f"Invalid quantity: {request.quantity}")
            return False

        # Price validation
        if request.price is not None and request.price <= 0:
            logger.warning(f"Invalid price: {request.price}")
            return False

        return True

    def _build_prompt(self, user_input: str) -> str:
        """Build the parsing prompt for the LLM."""
        return f"""Parse this user input into structured format:

User input: "{user_input}"

First, determine the request_type:
- "trade" = User wants to buy, sell, or analyze a specific ticker
  Examples: "buy AAPL", "is SPY good?", "sell my TSLA", "10 shares AAPL"
- "status_query" = User is asking about account status, orders, or positions
  Examples: "any open orders?", "what positions do I have?", "show my portfolio"
  Note: Words like "any", "what", "show", "check" at the start usually indicate status queries

If request_type is "trade", extract:
- ticker: Stock symbol (uppercase, 1-5 letters)
- action: IMPORTANT - Default to "review" (analyze) unless user explicitly says "buy" or "sell"
  * "buy AAPL" → action="buy"
  * "sell TSLA" → action="sell"
  * "10 AAPL" → action="review" (quantity alone = review, NOT buy!)
  * "AAPL" → action="review"
  * "is AAPL good?" → action="review"
- quantity: Number of shares if mentioned
- price: Price if mentioned (e.g., "at 600" means price=600)
- asset_type: "stock" (default) or "option"

If request_type is "status_query":
- ticker: Empty string (unless asking about specific ticker's position)
- action: "review" (default)

Use the parse_trade_request function."""

    def _autocorrect(self, user_input: str) -> str:
        """
        Auto-correct obvious errors in user input.

        Examples:
        - "spy at 60" -> "SPY at 600" (common price typos)
        """
        corrected = user_input

        # Common price typos (SPY at 60 -> 600, QQQ at 50 -> 500)
        common_corrections = {
            r"\bspy at 60\b": "SPY at 600",
            r"\bspy at 6([0-9]{2})\b": r"SPY at 6\1",
            r"\bqqq at 50\b": "QQQ at 500",
            r"\bqqq at 5([0-9]{2})\b": r"QQQ at 5\1",
        }

        for pattern, replacement in common_corrections.items():
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)

        if corrected != user_input:
            logger.info(f"Auto-corrected: '{user_input}' -> '{corrected}'")

        return corrected
