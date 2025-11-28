"""
LLM-based natural language parser.

Uses LLM (via LLMService) to parse conversational user input into structured TradeRequest.
"""

import logging
import re
from typing import Optional

from core.interfaces import InputParser
from core.models import AssetType, TradeRequest
from services.llm import LLMService

logger = logging.getLogger(__name__)


class LLMParser(InputParser):
    """
    Parse natural language input using LLM.

    Examples:
    - "is SPY at 600 good?" → TradeRequest(ticker="SPY", action="review", price=600)
    - "buy 50 AAPL" → TradeRequest(ticker="AAPL", action="buy", quantity=50)
    - "should I sell my TSLA?" → TradeRequest(ticker="TSLA", action="review")
    """

    def __init__(self, llm_service: LLMService):
        """
        Initialize with LLM service.

        Args:
            llm_service: LLM service for parsing
        """
        self.llm = llm_service
        logger.info(f"LLMParser initialized with {llm_service.provider.value}")

    async def parse(self, user_input: str, user_id: Optional[str] = None) -> TradeRequest:
        """
        Parse user input into TradeRequest using LLM.

        Args:
            user_input: Raw user input
            user_id: Optional user ID

        Returns:
            Parsed TradeRequest

        Raises:
            ValueError: If input cannot be parsed
        """
        # Auto-correct obvious errors first (e.g., "spy at 60" → "SPY at 600")
        corrected_input = self._autocorrect(user_input)

        # Define tool for LLM to use
        tools = [
            {
                "name": "parse_trade_request",
                "description": "Parse user's trade request into structured format",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "request_type": {
                            "type": "string",
                            "enum": ["trade", "status_query"],
                            "description": "Type of request: 'trade' for buy/sell/analyze ticker, 'status_query' for asking about orders/positions/portfolio",
                        },
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., SPY, AAPL, TSLA). Empty string if status_query with no specific ticker.",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["review", "buy", "sell"],
                            "description": "User's intent: review (analyze), buy, or sell",
                        },
                        "quantity": {
                            "type": "integer",
                            "description": "Number of shares (optional, null if not specified)",
                        },
                        "price": {
                            "type": "number",
                            "description": "Entry price mentioned (optional, null if not specified)",
                        },
                        "asset_type": {
                            "type": "string",
                            "enum": ["stock", "option"],
                            "description": "Asset type (default: stock)",
                        },
                        "timing": {
                            "type": "string",
                            "enum": ["now", "pullback", "dip", "breakout", "limit"],
                            "description": "Entry timing context: 'now' (immediate), 'pullback'/'dip' (wait for lower price), 'breakout' (wait for breakout), 'limit' (user specified exact price)",
                        },
                    },
                    "required": ["request_type", "ticker", "action"],
                },
            }
        ]

        # Prompt for LLM
        prompt = f"""Parse this user input into structured format:

User input: "{corrected_input}"

First, determine the request_type:
- "trade" = User wants to buy, sell, or analyze a specific ticker (e.g., "buy AAPL", "is SPY good?", "sell my TSLA")
- "status_query" = User is asking about their account status, orders, or positions WITHOUT specifying intent to trade
  Examples: "any open orders?", "what positions do I have?", "show my portfolio", "any open trades?"
  Note: Words like "any", "what", "show", "check" at the start usually indicate status queries, NOT ticker symbols!

If request_type is "trade", extract:
- ticker: Stock symbol
- action: Is user asking to review/analyze ("is X good?"), buy, or sell?
  IMPORTANT: The action is the user's DESIRED DIRECTION, not the timing.
  "buy QQQ at a pullback" → action="buy" (user wants to BUY, just at a lower price)
  "sell AAPL on a bounce" → action="sell" (user wants to SELL, just at a higher price)
- quantity: Number of shares if mentioned
- price: Specific price if mentioned (e.g., "at 600" means price=600)
- asset_type: "stock" (default) or "option" if user mentions options
- timing: Entry timing preference:
  - "now" = immediate execution, no timing preference mentioned
  - "pullback" or "dip" = user wants to enter at a LOWER price (buy the dip, wait for pullback)
  - "breakout" = user wants to enter after a price breakout (above resistance)
  - "limit" = user specified an exact price target

If request_type is "status_query":
- ticker: Empty string (unless asking about specific ticker's position)
- action: "review" (default)

Use the parse_trade_request function."""

        try:
            result = await self.llm.call_tool(prompt, tools, temperature=0.0)

            if not result or "arguments" not in result:
                raise ValueError(f"Failed to parse input: {user_input}")

            args = result["arguments"]

            # Create TradeRequest
            request = TradeRequest(
                ticker=args["ticker"].upper() if args["ticker"] else "",
                action=args["action"],
                request_type=args.get("request_type", "trade"),
                quantity=args.get("quantity"),
                price=args.get("price"),
                asset_type=AssetType(args.get("asset_type", "stock")),
                timing=args.get("timing"),  # Issue #344: entry timing context
                raw_input=user_input,
            )

            logger.info(
                f"Parsed: '{user_input}' → {request.action} {request.ticker}"
                + (f" qty={request.quantity}" if request.quantity else "")
                + (f" @{request.price}" if request.price else "")
                + (f" timing={request.timing}" if request.timing else "")
            )

            return request

        except Exception as e:
            logger.error(f"Parse error: {e}", exc_info=True)
            raise ValueError(f"Could not parse input: {user_input}") from e

    async def validate(self, request: TradeRequest) -> bool:
        """
        Validate parsed request.

        Args:
            request: Parsed TradeRequest

        Returns:
            True if valid

        Checks:
        - Ticker is valid format (1-5 uppercase letters)
        - Quantity is positive (if specified)
        - Price is positive (if specified)
        """
        # Ticker validation (basic)
        if not re.match(r"^[A-Z]{1,5}$", request.ticker):
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

    def _autocorrect(self, user_input: str) -> str:
        """
        Auto-correct obvious errors in user input.

        Examples:
        - "spy at 60" → "SPY at 600" (common price typos)
        - "aapl" → "AAPL" (uppercase tickers)

        Args:
            user_input: Raw input

        Returns:
            Corrected input
        """
        corrected = user_input

        # Common ticker typos (lowercase → uppercase handled by LLM)
        # Common price typos (SPY at 60 → 600, QQQ at 50 → 500)
        common_corrections = {
            r"\bspy at 60\b": "SPY at 600",
            r"\bspy at 6([0-9]{2})\b": r"SPY at 6\1",  # spy at 605 → SPY at 605
            r"\bqqq at 50\b": "QQQ at 500",
            r"\bqqq at 5([0-9]{2})\b": r"QQQ at 5\1",
        }

        for pattern, replacement in common_corrections.items():
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)

        if corrected != user_input:
            logger.info(f"Auto-corrected: '{user_input}' → '{corrected}'")

        return corrected
