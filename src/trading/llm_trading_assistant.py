#!/usr/bin/env python3
"""
LLM Trading Assistant - Human-in-Loop Interface

This module provides a conversational interface for trade management.
Human sends natural language requests, LLM interprets and executes trades.
"""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import time as dt_time
from enum import Enum
from typing import Any, Dict, Optional

import pytz

from src.utils.date_utils import get_datetime_now, now_iso

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData
from src.trading.alpaca_trading_client import AlpacaOrderManager

# Import your existing modules
from src.trading.simple_signals import SimpleSignalGenerator
from src.utils.agent_utils import load_agent_config

logger = logging.getLogger(__name__)


class RequestType(Enum):
    """Types of trading requests"""

    ADD_POSITION = "add_position"
    CLOSE_POSITION = "close_position"
    ADJUST_STOP = "adjust_stop"
    PORTFOLIO_STATUS = "portfolio_status"
    SCAN_OPPORTUNITIES = "scan_opportunities"
    EVALUATE_TICKER = "evaluate_ticker"
    UNKNOWN = "unknown"


@dataclass
class TradingRequest:
    """Parsed trading request from human"""

    request_type: RequestType
    symbol: Optional[str] = None
    action: Optional[str] = None  # buy/sell
    confidence: Optional[str] = None  # high/medium/low
    reason: Optional[str] = None
    raw_text: str = ""
    timestamp: str = ""


class LLMTradingAssistant:
    """
    Main interface for human-in-loop trading.
    Interprets natural language requests and executes trades.
    """

    def __init__(self, mode: str = "paper"):
        """
        Initialize the trading assistant.

        Args:
            mode: "paper" or "live" trading
        """
        self.mode = mode
        self.order_manager = AlpacaOrderManager(mode=mode)
        self.market_data = AlpacaMarketData()

        # Initialize voter agent
        # Initialize simple signal generator (replacing complex VoterAgent)
        self.signal_generator = SimpleSignalGenerator()

        # State management
        self.state_dir = "state"
        self.positions_file = os.path.join(self.state_dir, "llm_positions.json")
        self.request_log_file = os.path.join(self.state_dir, "request_log.json")

        # Trading parameters (from validated backtesting)
        self.position_rules = {
            "max_positions": 3,
            "max_position_pct": 0.33,  # 33% max per position
            "stop_loss_pct": 0.05,  # 5% stop loss
            "take_profit_pct": 0.08,  # 8% take profit
            "min_confidence": 0.65,  # Minimum voting confidence
        }

        # Ensure state directory exists
        os.makedirs(self.state_dir, exist_ok=True)

        logger.info(f"LLM Trading Assistant initialized in {mode} mode")

    def parse_request(self, user_input: str) -> TradingRequest:
        """
        Parse natural language request into structured format.

        This would ideally use an LLM, but for now uses keyword matching.
        In production, replace with GPT-4 call for better parsing.

        Args:
            user_input: Natural language request from user

        Returns:
            Parsed TradingRequest object
        """
        request = TradingRequest(
            request_type=RequestType.UNKNOWN,
            raw_text=user_input,
            timestamp=now_iso(),
        )

        # Convert to lowercase for matching
        lower_input = user_input.lower()

        # Parse request type and extract details
        if any(word in lower_input for word in ["add", "buy", "enter", "open"]):
            request.request_type = RequestType.ADD_POSITION
            # Extract ticker (simple regex for now)
            import re

            ticker_match = re.search(r"\b([A-Z]{2,5})\b", user_input)
            if ticker_match:
                request.symbol = ticker_match.group(1)

        elif any(word in lower_input for word in ["close", "sell", "exit"]):
            request.request_type = RequestType.CLOSE_POSITION
            import re

            ticker_match = re.search(r"\b([A-Z]{2,5})\b", user_input)
            if ticker_match:
                request.symbol = ticker_match.group(1)

        elif any(word in lower_input for word in ["stop", "adjust", "trail"]):
            request.request_type = RequestType.ADJUST_STOP
            import re

            ticker_match = re.search(r"\b([A-Z]{2,5})\b", user_input)
            if ticker_match:
                request.symbol = ticker_match.group(1)

        elif any(word in lower_input for word in ["status", "portfolio", "positions"]):
            request.request_type = RequestType.PORTFOLIO_STATUS

        elif any(word in lower_input for word in ["scan", "opportunities", "find"]):
            request.request_type = RequestType.SCAN_OPPORTUNITIES

        elif any(word in lower_input for word in ["evaluate", "check", "analyze"]):
            request.request_type = RequestType.EVALUATE_TICKER
            import re

            ticker_match = re.search(r"\b([A-Z]{2,5})\b", user_input)
            if ticker_match:
                request.symbol = ticker_match.group(1)

        # Extract confidence if mentioned
        if "high confidence" in lower_input or "strong" in lower_input:
            request.confidence = "high"
        elif "low confidence" in lower_input or "weak" in lower_input:
            request.confidence = "low"
        else:
            request.confidence = "medium"

        logger.info(f"Parsed request: {request.request_type} for {request.symbol}")
        return request

    def process_request(self, user_input: str) -> str:
        """
        Main entry point for processing user requests.

        Args:
            user_input: Natural language request from user

        Returns:
            Response message for the user
        """
        try:
            # Parse the request
            request = self.parse_request(user_input)

            # Log the request
            self.log_request(request)

            # Route to appropriate handler
            if request.request_type == RequestType.ADD_POSITION:
                return self.handle_add_position(request)

            elif request.request_type == RequestType.CLOSE_POSITION:
                return self.handle_close_position(request)

            elif request.request_type == RequestType.ADJUST_STOP:
                return self.handle_adjust_stop(request)

            elif request.request_type == RequestType.PORTFOLIO_STATUS:
                return self.handle_portfolio_status()

            elif request.request_type == RequestType.SCAN_OPPORTUNITIES:
                return self.handle_scan_opportunities()

            elif request.request_type == RequestType.EVALUATE_TICKER:
                return self.handle_evaluate_ticker(request)

            else:
                return self.handle_unknown_request(request)

        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return f"❌ Error processing request: {str(e)}\n\nPlease check logs for details."

    def handle_add_position(self, request: TradingRequest) -> str:
        """
        Handle request to add a new position.

        Args:
            request: Parsed trading request

        Returns:
            Response message
        """
        if not request.symbol:
            return "❌ No symbol specified. Please specify a ticker symbol (e.g., 'add TQQQ')"

        try:
            # Check current positions
            positions = self.get_current_positions()

            # Check if already in position
            if request.symbol in positions:
                return (
                    f"⚠️ Already in position for {request.symbol}\n"
                    f"Entry: ${positions[request.symbol]['avg_entry_price']:.2f}\n"
                    f"Shares: {positions[request.symbol]['qty']}\n"
                    f"P&L: ${positions[request.symbol]['unrealized_pl']:.2f}"
                )

            # Check position limits
            if len(positions) >= self.position_rules["max_positions"]:
                position_list = "\n".join(
                    [f"  • {sym}: ${pos['market_value']:.2f}" for sym, pos in positions.items()]
                )
                return (
                    f"❌ Maximum positions reached ({self.position_rules['max_positions']})\n\n"
                    f"Current positions:\n{position_list}\n\n"
                    f"Close a position first or wait for exits."
                )

            # Get technical signals from voter agent
            signals = self.evaluate_ticker_signals(request.symbol)

            # Check if signals are favorable
            if signals["vote_score"] < self.position_rules["min_confidence"]:
                response = f"❌ Weak signals for {request.symbol}\n\n"
                response += f"Vote Score: {signals['vote_score']:.2f} (need ≥ {self.position_rules['min_confidence']})\n"
                if "staleness_penalty" in signals and signals["staleness_penalty"] > 0:
                    response += f"  ⚠️ Confidence reduced by {signals['staleness_penalty']:.2f} due to stale data\n"
                response += f"MACD: {signals['macd_signal']}\n"
                response += f"RSI: {signals['rsi_value']:.1f}\n"
                if "data_source" in signals and signals["data_source"] != "live_alpaca":
                    response += f"Data Source: {signals['data_source']} (historical)\n"
                response += "\nRecommendation: Wait for better entry signals or market open"
                return response

            # Calculate position size
            account = self.order_manager.get_account_status()
            buying_power = float(account["buying_power"])
            current_price = self.get_current_price(request.symbol)

            max_position_value = min(
                buying_power * self.position_rules["max_position_pct"],
                5000,  # Cap at $5000 for safety
            )
            shares = int(max_position_value / current_price)

            if shares <= 0:
                return (
                    f"❌ Insufficient buying power\n"
                    f"Available: ${buying_power:.2f}\n"
                    f"Needed: ~${current_price * 10:.2f} (minimum)"
                )

            # Calculate stop and target prices
            stop_price = current_price * (1 - self.position_rules["stop_loss_pct"])
            target_price = current_price * (1 + self.position_rules["take_profit_pct"])

            # Place bracket order
            result = self.order_manager.place_bracket_order(
                symbol=request.symbol,
                qty=shares,
                side="buy",
                entry_limit_price=None,  # Market order
                take_profit_price=target_price,
                stop_loss_price=stop_price,
            )

            if result["status"] == "submitted":
                # Save to state
                self.update_position_state(
                    request.symbol,
                    {
                        "entry_price": current_price,
                        "stop_price": stop_price,
                        "target_price": target_price,
                        "shares": shares,
                        "signal_strength": signals["vote_score"],
                        "entry_time": now_iso(),
                    },
                )

                response = f"✅ **Position Opened: {request.symbol}**\n\n"
                response += "**Entry Details:**\n"
                response += f"  • Price: ${current_price:.2f}\n"
                response += f"  • Shares: {shares}\n"
                response += f"  • Value: ${current_price * shares:.2f}\n\n"
                response += "**Risk Management:**\n"
                response += f"  • Stop Loss: ${stop_price:.2f} (-5.0%)\n"
                response += f"  • Take Profit: ${target_price:.2f} (+8.0%)\n"
                response += f"  • Max Risk: ${(current_price - stop_price) * shares:.2f}\n"
                response += f"  • Max Reward: ${(target_price - current_price) * shares:.2f}\n\n"
                response += "**Signals:**\n"
                response += f"  • Vote Score: {signals['vote_score']:.2f}"
                if "staleness_penalty" in signals and signals["staleness_penalty"] > 0:
                    response += f" (reduced {signals['staleness_penalty']:.2f} for stale data)"
                response += "\n"
                response += f"  • MACD: {signals['macd_signal']}\n"
                response += f"  • RSI: {signals['rsi_value']:.1f}\n"
                if "data_source" in signals and signals["data_source"] != "live_alpaca":
                    response += f"  • Data: {signals['data_source']} (historical)\n"
                response += "\n"
                response += "📝 Orders submitted with GTC (Good Till Cancelled)"

                return response
            else:
                return f"❌ Failed to place order: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error adding position: {e}")
            return f"❌ Error adding position: {str(e)}"

    def handle_close_position(self, request: TradingRequest) -> str:
        """Handle request to close a position."""
        if not request.symbol:
            positions = self.get_current_positions()
            if not positions:
                return "📊 No open positions to close"

            position_list = "\n".join(
                [f"  • {sym}: ${pos['unrealized_pl']:.2f} P&L" for sym, pos in positions.items()]
            )
            return f"⚠️ Please specify which position to close:\n{position_list}"

        try:
            positions = self.get_current_positions()

            if request.symbol not in positions:
                return f"❌ No position found for {request.symbol}"

            position = positions[request.symbol]

            # Cancel existing stop/target orders
            orders = self.order_manager.get_orders(status="open")
            for order in orders:
                if order["symbol"] == request.symbol:
                    self.order_manager.cancel_order(order["id"])

            # Place market sell order
            result = self.order_manager.place_market_order(
                symbol=request.symbol, qty=position["qty"], side="sell"
            )

            if result["status"] == "submitted":
                pl = position["unrealized_pl"]
                pl_pct = (pl / position["cost_basis"]) * 100

                response = f"✅ **Closing Position: {request.symbol}**\n\n"
                response += "**Position Details:**\n"
                response += f"  • Entry: ${position['avg_entry_price']:.2f}\n"
                response += f"  • Current: ${current_price:.2f}\n"
                response += f"  • Shares: {position['qty']}\n\n"
                response += "**P&L:**\n"
                response += f"  • Dollar: ${pl:+.2f}\n"
                response += f"  • Percent: {pl_pct:+.1f}%\n\n"
                response += "📝 Market sell order submitted"

                # Remove from state
                self.remove_position_state(request.symbol)

                return response
            else:
                return f"❌ Failed to close position: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return f"❌ Error closing position: {str(e)}"

    def handle_adjust_stop(self, request: TradingRequest) -> str:
        """Handle request to adjust stop loss."""
        if not request.symbol:
            return "❌ Please specify which position to adjust (e.g., 'adjust stop for TQQQ')"

        try:
            positions = self.get_current_positions()

            if request.symbol not in positions:
                return f"❌ No position found for {request.symbol}"

            position = positions[request.symbol]
            # Calculate current price from market value and quantity
            current_price = (
                position["market_value"] / abs(position["qty"])
                if position["qty"] != 0
                else position["avg_entry_price"]
            )
            entry_price = position["avg_entry_price"]

            # Calculate profit percentage
            profit_pct = (current_price - entry_price) / entry_price

            # Determine new stop based on profit
            if profit_pct < 0.02:
                return (
                    f"ℹ️ Position {request.symbol} has {profit_pct:.1%} profit\n"
                    f"Stop remains at original level (adjust at 2%+ profit)"
                )

            elif profit_pct < 0.04:
                new_stop = entry_price  # Breakeven
                stop_label = "breakeven"
            elif profit_pct < 0.06:
                new_stop = entry_price + (current_price - entry_price) * 0.25
                stop_label = "25% profit lock"
            else:
                new_stop = entry_price + (current_price - entry_price) * 0.50
                stop_label = "50% trailing"

            # Find and modify stop order
            orders = self.order_manager.get_orders(status="open")
            stop_order = None
            for order in orders:
                if order["symbol"] == request.symbol and order["order_type"] == "stop":
                    stop_order = order
                    break

            if not stop_order:
                return f"⚠️ No stop order found for {request.symbol}"

            # Modify the stop order
            result = self.order_manager.modify_order(order_id=stop_order["id"], stop_price=new_stop)

            if result["status"] == "submitted":
                response = f"✅ **Stop Adjusted: {request.symbol}**\n\n"
                response += "**Position Status:**\n"
                response += f"  • Entry: ${entry_price:.2f}\n"
                response += f"  • Current: ${current_price:.2f}\n"
                response += f"  • Profit: {profit_pct:.1%}\n\n"
                response += "**Stop Update:**\n"
                response += f"  • Old Stop: ${stop_order['stop_price']:.2f}\n"
                response += f"  • New Stop: ${new_stop:.2f} ({stop_label})\n"
                response += (
                    f"  • Protected Profit: ${(new_stop - entry_price) * position['qty']:.2f}\n"
                )

                return response
            else:
                return f"❌ Failed to adjust stop: {result.get('message', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error adjusting stop: {e}")
            return f"❌ Error adjusting stop: {str(e)}"

    def handle_portfolio_status(self) -> str:
        """Generate portfolio status report."""
        try:
            # Get account info
            account = self.order_manager.get_account_status()

            # Get positions
            positions = self.get_current_positions()

            # Get open orders
            orders = self.order_manager.get_orders(status="open")

            # Build response
            response = "📊 **Portfolio Status**\n"
            response += "=" * 40 + "\n\n"

            # Account summary
            response += "**Account Summary:**\n"
            response += f"  • Equity: ${float(account['equity']):,.2f}\n"
            response += f"  • Cash: ${float(account['cash']):,.2f}\n"
            response += f"  • Buying Power: ${float(account['buying_power']):,.2f}\n"
            response += f"  • Day P&L: ${float(account.get('unrealized_intraday_pl', 0)):+,.2f}\n\n"

            # Positions
            if positions:
                response += f"**Open Positions ({len(positions)}/{self.position_rules['max_positions']}):**\n"
                total_pl = 0
                for symbol, pos in positions.items():
                    pl = pos["unrealized_pl"]
                    pl_pct = (pl / pos["cost_basis"]) * 100
                    total_pl += pl

                    current_price = (
                        pos["market_value"] / abs(pos["qty"])
                        if pos["qty"] != 0
                        else pos["avg_entry_price"]
                    )

                    response += f"\n{symbol}:\n"
                    response += f"  • Shares: {pos['qty']} @ ${pos['avg_entry_price']:.2f}\n"
                    response += f"  • Current: ${current_price:.2f}\n"
                    response += f"  • P&L: ${pl:+.2f} ({pl_pct:+.1f}%)\n"
                    response += f"  • Value: ${pos['market_value']:.2f}\n"

                response += f"\n**Total Unrealized P&L: ${total_pl:+.2f}**\n\n"
            else:
                response += "**No open positions**\n\n"

            # Open orders
            if orders:
                response += f"**Open Orders ({len(orders)}):**\n"
                for order in orders[:5]:  # Limit to 5 most recent
                    response += f"  • {order['symbol']}: {order['side']} {order['qty']} @ "
                    response += f"${order.get('limit_price', 'market')}\n"
            else:
                response += "**No open orders**\n"

            return response

        except Exception as e:
            logger.error(f"Error getting portfolio status: {e}")
            return f"❌ Error getting portfolio status: {str(e)}"

    def handle_scan_opportunities(self) -> str:
        """Scan for trading opportunities."""
        try:
            # Default watchlist for leveraged ETFs
            watchlist = ["TQQQ", "SQQQ", "SPXL", "SPXS", "UPRO", "SPXU"]

            response = "🔍 **Scanning Opportunities**\n"
            response += "=" * 40 + "\n\n"

            opportunities = []

            for symbol in watchlist:
                try:
                    signals = self.evaluate_ticker_signals(symbol)

                    if signals["vote_score"] >= self.position_rules["min_confidence"]:
                        opportunities.append(
                            {
                                "symbol": symbol,
                                "score": signals["vote_score"],
                                "macd": signals["macd_signal"],
                                "rsi": signals["rsi_value"],
                            }
                        )
                except Exception as e:
                    logger.error(f"Error scanning {symbol}: {e}")
                    continue

            if opportunities:
                # Sort by score
                opportunities.sort(key=lambda x: x["score"], reverse=True)

                response += "**Strong Signals Found:**\n\n"
                for opp in opportunities:
                    response += f"**{opp['symbol']}**\n"
                    response += f"  • Vote Score: {opp['score']:.2f}\n"
                    response += f"  • MACD: {opp['macd']}\n"
                    response += f"  • RSI: {opp['rsi']:.1f}\n\n"

                response += f"💡 Top pick: {opportunities[0]['symbol']}\n"
                response += f"Use 'add {opportunities[0]['symbol']}' to enter position"
            else:
                response += "No strong opportunities found in watchlist.\n"
                response += "All signals below minimum confidence threshold.\n\n"
                response += "Scanned: " + ", ".join(watchlist)

            return response

        except Exception as e:
            logger.error(f"Error scanning opportunities: {e}")
            return f"❌ Error scanning opportunities: {str(e)}"

    def handle_evaluate_ticker(self, request: TradingRequest) -> str:
        """Evaluate a specific ticker."""
        if not request.symbol:
            return "❌ Please specify a ticker to evaluate (e.g., 'evaluate TQQQ')"

        try:
            signals = self.evaluate_ticker_signals(request.symbol)
            current_price = self.get_current_price(request.symbol)

            response = f"📈 **Evaluation: {request.symbol}**\n"
            response += "=" * 40 + "\n\n"

            response += f"**Current Price:** ${current_price:.2f}\n\n"

            response += "**Technical Signals:**\n"
            response += f"  • Vote Score: {signals['vote_score']:.2f} "

            if signals["vote_score"] >= self.position_rules["min_confidence"]:
                response += "✅ STRONG"
            else:
                response += "❌ WEAK"

            if "staleness_penalty" in signals and signals["staleness_penalty"] > 0:
                response += f" (stale data penalty: -{signals['staleness_penalty']:.2f})"
            response += "\n"

            response += f"  • MACD: {signals['macd_signal']}\n"
            response += f"  • RSI: {signals['rsi_value']:.1f} "

            if signals["rsi_value"] > 70:
                response += "(Overbought)\n"
            elif signals["rsi_value"] < 30:
                response += "(Oversold)\n"
            else:
                response += "(Neutral)\n"

            # Add data source information
            if "data_source" in signals and signals["data_source"] != "live_alpaca":
                response += f"  • Data Source: {signals['data_source']} (historical)\n"
                if "market_status" in signals and not signals["market_status"]["is_open"]:
                    hours_stale = signals["market_status"]["hours_since_close"]
                    response += f"  • Data Age: {hours_stale:.1f} hours since market close\n"

            response += "\n**Recommendation:** "

            if signals["vote_score"] >= self.position_rules["min_confidence"]:
                response += "BUY - Strong signals\n"
                response += f"Suggested stop: ${current_price * 0.95:.2f} (-5%)\n"
                response += f"Suggested target: ${current_price * 1.08:.2f} (+8%)"
                if "data_source" in signals and signals["data_source"] != "live_alpaca":
                    response += (
                        "\n⚠️ Note: Based on historical data - verify with live market conditions"
                    )
            else:
                response += "WAIT - Signals not strong enough\n"
                response += f"Current vote {signals['vote_score']:.2f} < {self.position_rules['min_confidence']} threshold"
                if "staleness_penalty" in signals and signals["staleness_penalty"] > 0:
                    response += "\n💡 Consider retrying when market opens for fresh data"

            return response

        except Exception as e:
            logger.error(f"Error evaluating ticker: {e}")
            return f"❌ Error evaluating {request.symbol}: {str(e)}"

    def handle_unknown_request(self, request: TradingRequest) -> str:
        """Handle unknown request types."""
        # Load help text from YAML configuration
        interface_config = load_agent_config("interface")
        help_text = interface_config.get("llm_assistant", {}).get("help_text", "")

        # Fallback to default if YAML not available
        if not help_text:
            help_text = "❓ I didn't understand that request.\n\n"
            help_text += "**Available Commands:**\n"
            help_text += "  • `add [SYMBOL]` - Open a new position\n"
            help_text += "  • `close [SYMBOL]` - Close a position\n"
            help_text += "  • `adjust stop [SYMBOL]` - Adjust stop loss\n"
            help_text += "  • `status` - Show portfolio status\n"
            help_text += "  • `scan` - Scan for opportunities\n"
            help_text += "  • `evaluate [SYMBOL]` - Evaluate a ticker\n\n"
            help_text += "**Examples:**\n"
            help_text += "  • 'add TQQQ'\n"
            help_text += "  • 'close all positions'\n"
            help_text += "  • 'what's my portfolio status?'\n"
            help_text += "  • 'scan for opportunities'"

        return help_text

    # Helper methods

    def _get_market_status(self) -> Dict[str, Any]:
        """
        Determine current market status and data freshness.

        Returns:
            Dict with market open status, last trading day, hours since close
        """
        try:
            # US Eastern Time
            et = pytz.timezone("US/Eastern")
            now_et = get_datetime_now(et)

            # Market hours: 9:30 AM - 4:00 PM ET, Monday-Friday
            market_open_time = dt_time(9, 30)
            market_close_time = dt_time(16, 0)

            # Check if today is a weekday
            is_weekday = now_et.weekday() < 5  # Monday = 0, Friday = 4

            # Check if within market hours
            current_time = now_et.time()
            is_market_hours = market_open_time <= current_time <= market_close_time

            is_market_open = is_weekday and is_market_hours

            # Calculate last trading day and staleness
            if is_market_open:
                last_trading_day = now_et.date()
                hours_since_close = 0
            else:
                # Find the last trading day
                days_back = 0
                check_date = now_et

                while True:
                    if check_date.weekday() < 5:  # Weekday
                        if check_date.date() == now_et.date() and current_time < market_open_time:
                            # Today but before market open, use previous day
                            days_back += 1
                            check_date = check_date.replace(day=check_date.day - 1)
                            continue
                        else:
                            last_trading_day = check_date.date()
                            break
                    else:
                        # Weekend, go back
                        days_back += 1
                        check_date = check_date.replace(day=check_date.day - 1)

                # Calculate hours since market close
                if check_date.date() == now_et.date():
                    # Same day, market closed
                    market_close_dt = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
                    hours_since_close = (now_et - market_close_dt).total_seconds() / 3600
                else:
                    # Different day
                    market_close_dt = check_date.replace(hour=16, minute=0, second=0, microsecond=0)
                    hours_since_close = (now_et - market_close_dt).total_seconds() / 3600

            return {
                "is_open": is_market_open,
                "last_trading_day": last_trading_day.isoformat(),
                "hours_since_close": max(0, hours_since_close),
                "current_time_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "data_freshness": (
                    "live" if is_market_open else ("stale" if hours_since_close > 24 else "recent")
                ),
            }

        except Exception as e:
            logger.error(f"Error determining market status: {e}")
            # Fallback - assume market closed
            return {
                "is_open": False,
                "last_trading_day": get_datetime_now().date().isoformat(),
                "hours_since_close": 24,
                "current_time_et": "unknown",
                "data_freshness": "stale",
            }

    def get_current_positions(self) -> Dict[str, Any]:
        """Get current positions from broker."""
        try:
            positions = self.order_manager.get_positions()
            return {pos["symbol"]: pos for pos in positions}
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return {}

    def get_current_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        try:
            # Use the market data client to get real prices
            trade_data = self.market_data.get_latest_trade(symbol)
            if trade_data and "price" in trade_data:
                return float(trade_data["price"])

            # Fallback to quote mid-price
            quote_data = self.market_data.get_latest_quote(symbol)
            if quote_data and "bid_price" in quote_data and "ask_price" in quote_data:
                return (float(quote_data["bid_price"]) + float(quote_data["ask_price"])) / 2

        except Exception as e:
            logger.error(f"Error getting price for {symbol}: {e}")

        # Fallback prices for testing
        default_prices = {"TQQQ": 85.50, "SQQQ": 12.30, "SPXL": 140.00, "SPXS": 10.50}
        return default_prices.get(symbol, 50.0)

    def evaluate_ticker_signals(self, symbol: str) -> Dict[str, Any]:
        """
        Get technical signals using simple signal generator.

        Returns:
            Dictionary with signal data and market context
        """
        try:
            # Get market data for signal generation
            from datetime import timedelta

            end_date = get_datetime_now()
            start_date = end_date - timedelta(days=60)  # More data for reliable indicators

            # Check market status to determine data freshness
            market_status = self._get_market_status()

            # Get price data from market data client
            price_data = self.market_data.get_bars(
                symbols=[symbol],
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                timeframe="1Day",
            )

            if price_data.empty:
                logger.warning(f"No price data available for {symbol}")
                return self._create_fallback_signals(symbol, "No price data")

            # Generate signal using simple threshold-based system
            signal_result = self.signal_generator.evaluate_signal(price_data, symbol)

            # Add market context and data freshness
            signal_result.update(
                {
                    "market_context": {
                        "market_open": market_status["is_open"],
                        "data_source": (
                            "live_alpaca" if market_status["is_open"] else "historical_polygon"
                        ),
                        "last_trading_day": market_status["last_trading_day"],
                        "hours_since_close": market_status["hours_since_close"],
                        "data_freshness": market_status["data_freshness"],
                    },
                    "symbol": symbol,
                    "data_points": len(price_data),
                }
            )

            # Apply staleness penalty (CRITICAL FIX: Don't penalize recent historical data)
            # Our validated backtests used historical data - it's not inherently "stale"!
            staleness_penalty = 0.0

            # Only penalize truly ancient data (over 1 week old)
            if not market_status["is_open"]:
                hours_stale = market_status["hours_since_close"]
                if hours_stale > (7 * 24):  # More than 1 week old
                    staleness_penalty = 0.15
                    signal_result["confidence"] = max(
                        0.1, signal_result["confidence"] - staleness_penalty
                    )
                    signal_result["reason"] += f" | STALE DATA PENALTY: {staleness_penalty:.2f}"

            # Convert to legacy format for compatibility
            raw_data = signal_result.get("raw_data", {})
            return {
                "vote_score": signal_result["confidence"],
                "macd_signal": signal_result["action"],
                "rsi_value": raw_data.get("rsi", 50.0),
                "market_status": market_status,
                "data_source": signal_result["market_context"]["data_source"],
                "staleness_penalty": staleness_penalty,
                "raw_result": signal_result,
                "reason": signal_result["reason"],
            }

        except Exception as e:
            logger.error(f"Error evaluating signals for {symbol}: {e}")
            return self._create_fallback_signals(symbol, f"Error: {str(e)}")

    def _create_fallback_signals(self, symbol: str, reason: str) -> Dict[str, Any]:
        """Create fallback signals when evaluation fails."""
        logger.warning(f"Using fallback signals for {symbol}: {reason}")
        return {
            "vote_score": 0.5,
            "macd_signal": "HOLD",
            "rsi_value": 50.0,
            "market_status": self._get_market_status(),
            "data_source": "fallback",
            "staleness_penalty": 0.0,
            "raw_result": {},
            "reason": f"Fallback: {reason}",
        }

    def update_position_state(self, symbol: str, data: Dict[str, Any]):
        """Update position state in JSON."""
        try:
            states = {}
            if os.path.exists(self.positions_file):
                with open(self.positions_file, "r") as f:
                    states = json.load(f)

            states[symbol] = data

            with open(self.positions_file, "w") as f:
                json.dump(states, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error updating position state: {e}")

    def remove_position_state(self, symbol: str):
        """Remove position from state."""
        try:
            states = {}
            if os.path.exists(self.positions_file):
                with open(self.positions_file, "r") as f:
                    states = json.load(f)

            if symbol in states:
                del states[symbol]

            with open(self.positions_file, "w") as f:
                json.dump(states, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error removing position state: {e}")

    def log_request(self, request: TradingRequest):
        """Log request for audit trail."""
        try:
            logs = []
            if os.path.exists(self.request_log_file):
                with open(self.request_log_file, "r") as f:
                    logs = json.load(f)

            logs.append(asdict(request))

            # Keep last 100 requests
            logs = logs[-100:]

            with open(self.request_log_file, "w") as f:
                json.dump(logs, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error logging request: {e}")


# CLI Interface
def main():
    """
    Simple CLI interface for the trading assistant.
    """
    print("=" * 50)
    print("LLM Trading Assistant - Paper Trading Mode")
    print("=" * 50)
    print("\nType 'help' for commands, 'quit' to exit\n")

    # Initialize assistant
    assistant = LLMTradingAssistant(mode="paper")

    while True:
        try:
            # Get user input
            user_input = input("\n📊 Trading> ").strip()

            # Check for exit
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            # Process request
            response = assistant.process_request(user_input)

            # Display response
            print("\n" + response)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            logger.error(f"CLI error: {e}")


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler("trading_assistant.log"), logging.StreamHandler()],
    )

    # Run CLI
    main()
