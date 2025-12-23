"""
Intent Classification for CLI Session.

Issue #509: Extracted from cli_session.py for modularity.
Handles LLM-based intent classification and ticker resolution.
"""

import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class IntentClassifier:
    """
    Classifies user intent and resolves company names to tickers using LLM.

    Uses pattern matching for fast classification and gpt-4o-mini for
    company name to ticker resolution.
    """

    # Intent keywords for fast pattern matching
    BUY_WORDS = ["buy", "purchase", "long"]
    SELL_WORDS = ["sell", "short"]
    PORTFOLIO_WORDS = ["position", "holding", "portfolio", "account", "check", "show", "status"]
    ORDER_WORDS = ["order", "pending", "open"]
    ALERT_WORDS = ["alert", "watch"]
    SCHEDULER_WORDS = ["schedule", "scheduler", "daemon", "background"]
    ACCOUNT_WORDS = ["account", "switch", "list account", "change account", "accounts"]
    TIMEFRAME_WORDS = [
        "timeframe",
        "interval",
        "change timeframe",
        "set timeframe",
        "5m",
        "15m",
        "30m",
        "1h",
        "4h",
        "1d",
        "1w",
        "1m",
    ]
    HELP_WORDS = ["help", "what", "how", "command"]

    def __init__(self, orchestrator: Any = None, ticker_completer: Any = None):
        """
        Initialize the intent classifier.

        Args:
            orchestrator: TradingOrchestrator for LLM access
            ticker_completer: Optional ticker completer for autocomplete
        """
        self.orchestrator = orchestrator
        self.ticker_completer = ticker_completer

    async def classify_intent(self, user_input: str) -> Dict[str, Any]:  # noqa: C901
        """
        Use LLM to classify user intent and resolve company names to tickers dynamically.

        Returns:
            {
                'intent': 'trade_request' | 'portfolio_status' | 'open_orders' | 'alerts' | 'scheduler',
                'ticker': str | None,
                'company_name': str | None,
                'action': 'buy' | 'sell' | 'status' | None,
                'confidence': float
            }

        Issue #361: LLM-based intent classification with company name resolution
        Uses gpt-4o-mini (cheapest model) for structured output.
        """
        try:
            lower_input = user_input.lower()

            # Check if this looks like a trade request with a company/ticker name
            has_buy = any(
                word in lower_input for word in ["buy", "purchase", "long", "sell", "short"]
            )

            intent = "unknown"
            action = None
            ticker = None
            company_name = None
            confidence = 0.0

            # First pass: Pattern detection for intent (fast)
            if any(word in lower_input for word in self.BUY_WORDS):
                intent = "trade_request"
                action = "buy"
                confidence = 0.7

            elif any(word in lower_input for word in self.SELL_WORDS):
                intent = "trade_request"
                action = "sell"
                confidence = 0.7

            elif any(word in lower_input for word in self.PORTFOLIO_WORDS):
                intent = "portfolio_status"
                confidence = 0.85

            elif any(word in lower_input for word in self.ORDER_WORDS):
                intent = "open_orders"
                confidence = 0.85

            elif any(word in lower_input for word in self.ALERT_WORDS):
                intent = "alerts"
                confidence = 0.85

            elif any(word in lower_input for word in self.SCHEDULER_WORDS):
                intent = "scheduler"
                confidence = 0.85

            elif any(word in lower_input for word in self.ACCOUNT_WORDS):
                # Issue #401: Account management
                intent = "account_management"
                confidence = 0.85

            elif any(word in lower_input for word in self.TIMEFRAME_WORDS):
                # Issue #365: Timeframe management
                intent = "timeframe_management"
                confidence = 0.85

            elif any(word in lower_input for word in self.HELP_WORDS):
                intent = "help"
                confidence = 0.85

            # If it's a trade request, use LLM to extract/resolve ticker
            if intent == "trade_request" and (action or has_buy):
                ticker, company_name = await self.resolve_ticker_with_llm(user_input)
                if ticker:
                    confidence = 0.95  # High confidence if LLM resolved it
                else:
                    confidence = 0.7  # Lower if couldn't resolve

            logger.debug(
                f"Classified intent: {intent} (action={action}, ticker={ticker}, "
                f"company={company_name}, confidence={confidence})"
            )

            return {
                "intent": intent,
                "ticker": ticker,
                "company_name": company_name,
                "action": action,
                "confidence": confidence,
            }

        except (ValueError, AttributeError, OSError, RuntimeError) as e:
            logger.error(f"Error classifying intent: {e}", exc_info=True)
            return {
                "intent": "unknown",
                "ticker": None,
                "company_name": None,
                "action": None,
                "confidence": 0.0,
            }

    async def resolve_ticker_with_llm(  # noqa: C901
        self, user_input: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Use LLM (gpt-4o-mini) to extract company name and resolve to ticker.

        Uses cheap model to dynamically resolve any company name to ticker.
        Cost: ~$0.15 per 1M tokens with gpt-4o-mini.

        Args:
            user_input: User's command (e.g., "buy apple at $150")

        Returns:
            (ticker, company_name) tuple. Both None if couldn't resolve.
        """
        try:
            # Construct a lean prompt for the cheap LLM
            system_prompt = """You are a stock ticker resolver. Extract the company name from the user's input
and resolve it to its stock ticker symbol.

Return ONLY valid JSON with no extra text:
{
    "company_name": "Apple Inc.",
    "ticker": "AAPL",
    "found": true
}

If no company/ticker found:
{
    "company_name": null,
    "ticker": null,
    "found": false
}

Scope: Only resolve to real, tradable companies. Return found=false for ambiguous/invalid inputs."""

            user_prompt = f"Extract ticker from: {user_input}"

            # Call the LLM through the orchestrator
            if self.orchestrator and self.orchestrator.input_parser:
                try:
                    # Use the parser's LLM service with gpt-4o-mini (cheapest)
                    llm_service = self.orchestrator.input_parser.llm_service

                    response = await llm_service.call_structured(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model="gpt-4o-mini",  # Cheapest OpenAI model
                        timeout=2.0,  # 2 second timeout
                    )

                    # Parse the response
                    if isinstance(response, str):
                        data = json.loads(response)
                    else:
                        data = response

                    if data.get("found"):
                        ticker = data.get("ticker")
                        # Issue #399: Track resolved ticker for autocomplete
                        if ticker and self.ticker_completer:
                            self.ticker_completer.add_ticker(ticker)
                        return ticker, data.get("company_name")

                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse LLM response as JSON: {response}")
                except asyncio.TimeoutError:
                    logger.warning("LLM call timed out, falling back to pattern matching")
                except (ValueError, OSError, RuntimeError, AttributeError) as e:
                    logger.warning(f"LLM resolution failed: {e}")

            # Fallback: Try pattern matching for common formats
            # User might type "$AAPL" or just "AAPL"
            ticker_match = re.search(r"([A-Z]{1,5})", user_input)
            if ticker_match:
                potential_ticker = ticker_match.group(1)
                # Basic validation: 1-5 letters
                if 1 <= len(potential_ticker) <= 5 and potential_ticker.isalpha():
                    # Issue #399: Track resolved ticker for autocomplete
                    if self.ticker_completer:
                        self.ticker_completer.add_ticker(potential_ticker)
                    return potential_ticker, None

            return None, None

        except (ValueError, OSError, RuntimeError, AttributeError) as e:
            logger.error(f"Error resolving ticker with LLM: {e}")
            return None, None
