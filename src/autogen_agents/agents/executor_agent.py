#!/usr/bin/env python3
"""
ExecutorAgent - Trade Execution Coordination Agent

Handles trade execution, order management, and fill monitoring.
Coordinates with RiskAgent for pre-trade validation and publishes
execution events via AgentBus.

Issue #388: ExecutorAgent - Trade Execution Coordination
"""

import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from config_defaults.trading_config import TradingConfig

from ..core.base_agent import BaseAgent

# Agent Bus for event publishing (Issue #390)
from ..orchestration.agent_bus import EventType, create_message, get_agent_bus
from src.utils.agent_utils import load_agent_config
from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


class ExecutorAgent(BaseAgent):
    """
    Trade execution coordination agent.

    Responsibilities:
    - Place market, limit, stop, and bracket orders
    - Track pending orders and monitor fills
    - Handle order lifecycle transitions
    - Publish execution events via AgentBus
    - Coordinate with RiskAgent for pre-trade validation

    Integrates with existing OrderManager for broker communication.
    """

    def __init__(
        self,
        name: str = "executor_agent",
        initial_capital: float = 100000,
        order_manager: Optional[Any] = None,
        position_manager: Optional[Any] = None,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.08,
        paper_trading: bool = True,
        **kwargs,
    ):
        """
        Initialize ExecutorAgent.

        Args:
            name: Agent identifier
            initial_capital: Starting capital for paper trading
            order_manager: OrderManager instance (lazy loaded if None)
            position_manager: PositionManager instance (lazy loaded if None)
            stop_loss_pct: Default stop loss percentage
            take_profit_pct: Default take profit percentage
            paper_trading: Whether to use paper trading mode
            **kwargs: Additional BaseAgent parameters
        """
        super().__init__(name=name, **kwargs)

        self.initial_capital = initial_capital
        self.available_capital = initial_capital
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.paper_trading = paper_trading

        # Lazy-loaded broker components
        self._order_manager = order_manager
        self._position_manager = position_manager
        self._broker_client = None

        # Trading state
        self.pending_orders: Dict[str, Dict[str, Any]] = {}
        self.executed_trades: List[Dict[str, Any]] = []
        self.positions: Dict[str, Dict[str, Any]] = {}

        # Load config
        self.config = TradingConfig()

        # Agent Bus for event publishing
        self._bus = get_agent_bus()
        self._publish_events = True

        logger.info(f"ExecutorAgent '{name}' initialized:")
        logger.info(f"  Initial Capital: ${initial_capital:,.2f}")
        logger.info(f"  Stop Loss: {stop_loss_pct:.1%}")
        logger.info(f"  Take Profit: {take_profit_pct:.1%}")
        logger.info(f"  Paper Trading: {paper_trading}")

    def _get_order_manager(self):
        """Lazy load OrderManager if not provided."""
        if self._order_manager is None:
            try:
                from src.trading.alpaca_trading_client import get_trading_client
                from src.trading.order_manager import OrderManager
                from src.trading.position_manager import PositionManager

                self._broker_client = get_trading_client(paper=self.paper_trading)
                self._position_manager = PositionManager(self._broker_client)
                self._order_manager = OrderManager(self._broker_client, self._position_manager)
                logger.info("OrderManager initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize OrderManager: {e}")
                logger.warning("Running in simulation mode without broker connection")
        return self._order_manager

    def _get_position_manager(self):
        """Lazy load PositionManager if not provided."""
        if self._position_manager is None:
            self._get_order_manager()  # This also initializes position_manager
        return self._position_manager

    # ==================== Order Execution Methods ====================

    def execute_trade(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a trade order.

        Args:
            symbol: Ticker symbol
            side: 'buy' or 'sell'
            quantity: Number of shares
            order_type: 'market', 'limit', 'bracket'
            limit_price: Limit price (for limit orders)
            stop_price: Stop loss price (for bracket orders)
            take_profit_price: Take profit price (for bracket orders)
            correlation_id: ID to correlate related events

        Returns:
            Execution result with order details
        """
        logger.info(f"Executing {order_type} order: {side.upper()} {quantity} {symbol}")

        result = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "status": "pending",
            "timestamp": now_iso(),
            "correlation_id": correlation_id,
        }

        try:
            order_manager = self._get_order_manager()

            if order_manager is None:
                # Simulation mode
                result = self._simulate_execution(
                    symbol, side, quantity, order_type, limit_price, stop_price, take_profit_price
                )
            elif order_type == "bracket":
                # Bracket order with stop loss and take profit
                result = self._execute_bracket_order(
                    symbol, quantity, stop_price, take_profit_price
                )
            elif order_type == "limit" and limit_price:
                # Limit order
                order_result = order_manager.place_limit_order(symbol, quantity, side, limit_price)
                result.update(order_result)
            else:
                # Market order (default)
                order_result = order_manager.place_market_order(symbol, quantity, side)
                result.update(order_result)

            # Track pending order
            if result.get("id"):
                self.pending_orders[result["id"]] = result

            # Publish trade execution event
            if self._publish_events:
                self._publish_trade_event(result, correlation_id)

            result["status"] = "submitted"
            self.executed_trades.append(result)

            logger.info(f"Order submitted: {result.get('id', 'N/A')}")
            return result

        except Exception as e:
            logger.error(f"Execution failed for {symbol}: {e}")
            result["status"] = "failed"
            result["error"] = str(e)

            # Publish failure event
            if self._publish_events:
                self._publish_failure_event(result, str(e), correlation_id)

            return result

    def _execute_bracket_order(
        self,
        symbol: str,
        quantity: int,
        stop_price: Optional[float],
        take_profit_price: Optional[float],
    ) -> Dict[str, Any]:
        """Execute a bracket order with entry, stop, and target."""
        order_manager = self._get_order_manager()

        if order_manager is None:
            return {"error": "OrderManager not available"}

        # Calculate stop/target from config if not provided
        if stop_price is None or take_profit_price is None:
            # Get current price for calculation
            current_price = self._get_current_price(symbol)
            if current_price:
                stop_price = stop_price or round(current_price * (1 - self.stop_loss_pct), 2)
                take_profit_price = take_profit_price or round(
                    current_price * (1 + self.take_profit_pct), 2
                )
            else:
                return {"error": "Cannot calculate bracket prices without current price"}

        result = order_manager.place_bracket_order(symbol, quantity, stop_price, take_profit_price)

        return result

    def _simulate_execution(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        take_profit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Simulate order execution for paper trading without broker."""
        import uuid

        # Get simulated price
        current_price = self._get_current_price(symbol) or 100.0

        order_id = str(uuid.uuid4())[:8]

        result = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": quantity,
            "order_type": order_type,
            "status": "filled",  # Simulate immediate fill
            "filled_price": current_price,
            "filled_qty": quantity,
            "filled_at": now_iso(),
            "simulated": True,
        }

        # Update paper trading state
        if side.lower() == "buy":
            cost = current_price * quantity
            self.available_capital -= cost
            self.positions[symbol] = {
                "symbol": symbol,
                "qty": quantity,
                "entry_price": current_price,
                "current_price": current_price,
                "unrealized_pnl": 0,
                "stop_price": stop_price,
                "take_profit_price": take_profit_price,
            }
        elif side.lower() == "sell" and symbol in self.positions:
            position = self.positions.pop(symbol)
            proceeds = current_price * quantity
            self.available_capital += proceeds
            result["realized_pnl"] = (current_price - position["entry_price"]) * quantity

        logger.info(f"Simulated execution: {side} {quantity} {symbol} @ ${current_price:.2f}")
        return result

    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol."""
        try:
            from src.trading.unified_price_fetcher import UnifiedPriceFetcher

            fetcher = UnifiedPriceFetcher()
            price = fetcher.get_current_price(symbol)
            return price if price and price > 0 else None
        except Exception as e:
            logger.warning(f"Could not fetch price for {symbol}: {e}")
            return None

    # ==================== Order Management Methods ====================

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order_manager = self._get_order_manager()

        if order_manager is None:
            # Simulation mode - just remove from pending
            if order_id in self.pending_orders:
                self.pending_orders.pop(order_id)
                logger.info(f"Simulated cancel for order {order_id}")
                return True
            return False

        success = order_manager.cancel_order(order_id)
        if success:
            self.pending_orders.pop(order_id, None)
        return success

    def cancel_all_orders(self) -> int:
        """Cancel all pending orders."""
        order_manager = self._get_order_manager()

        if order_manager is None:
            count = len(self.pending_orders)
            self.pending_orders.clear()
            return count

        count = order_manager.cancel_all_orders()
        self.pending_orders.clear()
        return count

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an order."""
        order_manager = self._get_order_manager()

        if order_manager is None:
            return self.pending_orders.get(order_id)

        return order_manager.get_order_status(order_id)

    def monitor_fills(self) -> List[Dict[str, Any]]:
        """Monitor pending orders for fills."""
        order_manager = self._get_order_manager()

        if order_manager is None:
            return []  # No fills in simulation mode

        filled_orders = order_manager.monitor_order_fills()

        for fill in filled_orders:
            # Remove from pending
            order_id = fill.get("id")
            if order_id:
                self.pending_orders.pop(order_id, None)

            # Publish fill event
            if self._publish_events:
                self._publish_fill_event(fill)

        return filled_orders

    # ==================== Position Management Methods ====================

    def get_positions(self) -> Dict[str, Any]:
        """Get current positions."""
        position_manager = self._get_position_manager()

        if position_manager is None:
            return {
                "active_positions": list(self.positions.values()),
                "total_positions": len(self.positions),
                "source": "simulation",
            }

        try:
            positions = position_manager.get_all_positions()
            return {
                "active_positions": positions,
                "total_positions": len(positions),
                "source": "broker",
            }
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return {
                "active_positions": [],
                "total_positions": 0,
                "error": str(e),
            }

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position for a specific symbol."""
        position_manager = self._get_position_manager()

        if position_manager is None:
            return self.positions.get(symbol)

        try:
            return position_manager.get_position(symbol)
        except Exception as e:
            logger.error(f"Error fetching position for {symbol}: {e}")
            return None

    def update_positions(self, current_prices: Dict[str, float]) -> Dict[str, Any]:
        """Update positions with current prices and check for exits."""
        updates = {
            "updated": [],
            "triggered_exits": [],
            "timestamp": now_iso(),
        }

        for symbol, price in current_prices.items():
            position = self.get_position(symbol)
            if position:
                # Update current price
                position["current_price"] = price
                entry_price = position.get("entry_price", price)
                qty = position.get("qty", 0)
                position["unrealized_pnl"] = (price - entry_price) * qty

                updates["updated"].append(symbol)

                # Check stop loss
                stop_price = position.get("stop_price")
                if stop_price and price <= stop_price:
                    updates["triggered_exits"].append(
                        {
                            "symbol": symbol,
                            "trigger": "stop_loss",
                            "price": price,
                            "stop_price": stop_price,
                        }
                    )

                # Check take profit
                take_profit = position.get("take_profit_price")
                if take_profit and price >= take_profit:
                    updates["triggered_exits"].append(
                        {
                            "symbol": symbol,
                            "trigger": "take_profit",
                            "price": price,
                            "target_price": take_profit,
                        }
                    )

        return updates

    # ==================== Account Status Methods ====================

    def get_account_status(self) -> Dict[str, Any]:
        """Get account status including capital and positions."""
        positions_info = self.get_positions()
        positions = positions_info.get("active_positions", [])

        # Calculate position value
        position_value = sum(
            p.get("current_price", p.get("entry_price", 0)) * p.get("qty", 0) for p in positions
        )

        # Calculate unrealized P&L
        unrealized_pnl = sum(p.get("unrealized_pnl", 0) for p in positions)

        # Calculate realized P&L from executed trades
        realized_pnl = sum(t.get("realized_pnl", 0) for t in self.executed_trades)

        total_value = self.available_capital + position_value

        return {
            "initial_capital": self.initial_capital,
            "available_cash": self.available_capital,
            "position_value": position_value,
            "total_value": total_value,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "total_return_pct": (total_value - self.initial_capital) / self.initial_capital,
            "num_positions": len(positions),
            "num_pending_orders": len(self.pending_orders),
            "timestamp": now_iso(),
        }

    # ==================== Event Publishing Methods ====================

    def _publish_trade_event(
        self, result: Dict[str, Any], correlation_id: Optional[str] = None
    ) -> None:
        """Publish trade execution event."""
        try:
            msg = create_message(
                source_agent=self.name,
                event_type=EventType.TRADE_EXECUTED,
                symbol=result.get("symbol"),
                payload={
                    "order_id": result.get("id"),
                    "side": result.get("side"),
                    "quantity": result.get("qty"),
                    "order_type": result.get("order_type"),
                    "status": result.get("status"),
                },
                correlation_id=correlation_id,
            )
            self._bus.publish_sync(msg)
            logger.debug(f"Published TRADE_EXECUTED for {result.get('symbol')}")
        except Exception as e:
            logger.warning(f"Failed to publish trade event: {e}")

    def _publish_fill_event(self, fill: Dict[str, Any]) -> None:
        """Publish order fill event."""
        try:
            msg = create_message(
                source_agent=self.name,
                event_type=EventType.POSITION_OPENED,
                symbol=fill.get("symbol"),
                payload={
                    "order_id": fill.get("id"),
                    "filled_price": fill.get("filled_price"),
                    "filled_qty": fill.get("filled_qty"),
                    "side": fill.get("side"),
                },
            )
            self._bus.publish_sync(msg)
            logger.debug(f"Published POSITION_OPENED for {fill.get('symbol')}")
        except Exception as e:
            logger.warning(f"Failed to publish fill event: {e}")

    def _publish_failure_event(
        self, result: Dict[str, Any], error: str, correlation_id: Optional[str] = None
    ) -> None:
        """Publish trade failure event."""
        try:
            msg = create_message(
                source_agent=self.name,
                event_type=EventType.TRADE_FAILED,
                symbol=result.get("symbol"),
                payload={
                    "error": error,
                    "side": result.get("side"),
                    "quantity": result.get("quantity"),
                },
                correlation_id=correlation_id,
            )
            self._bus.publish_sync(msg)
            logger.debug(f"Published TRADE_FAILED for {result.get('symbol')}")
        except Exception as e:
            logger.warning(f"Failed to publish failure event: {e}")

    def set_publish_events(self, enabled: bool) -> None:
        """Enable or disable event publishing."""
        self._publish_events = enabled

    # ==================== AutoGen Interface ====================

    def generate_reply(self, messages, context=None) -> str:  # noqa: C901
        """
        AutoGen's required method for handling incoming messages.

        Expected message formats:
        - {"command": "execute", "symbol": "AAPL", "side": "buy", "quantity": 10}
        - {"command": "cancel", "order_id": "abc123"}
        - {"command": "status"}
        - {"command": "positions"}
        """
        if not messages:
            return json.dumps({"error": "No messages to process"})

        # Get the latest message
        latest_message = messages[-1]
        if hasattr(latest_message, "content"):
            content = latest_message.content
        else:
            content = str(latest_message)

        # Try to parse as JSON
        try:
            if isinstance(content, str):
                command_data = json.loads(content)
            else:
                command_data = content

            command = command_data.get("command", "status")

            if command == "execute":
                result = self.execute_trade(
                    symbol=command_data.get("symbol"),
                    side=command_data.get("side", "buy"),
                    quantity=command_data.get("quantity", 1),
                    order_type=command_data.get("order_type", "market"),
                    limit_price=command_data.get("limit_price"),
                    stop_price=command_data.get("stop_price"),
                    take_profit_price=command_data.get("take_profit_price"),
                )
                return json.dumps(result, indent=2)

            elif command == "cancel":
                order_id = command_data.get("order_id")
                if order_id:
                    success = self.cancel_order(order_id)
                    return json.dumps({"success": success, "order_id": order_id})
                else:
                    return json.dumps({"error": "order_id required"})

            elif command == "cancel_all":
                count = self.cancel_all_orders()
                return json.dumps({"cancelled": count})

            elif command == "positions":
                return json.dumps(self.get_positions(), indent=2)

            elif command == "status":
                return json.dumps(self.get_account_status(), indent=2)

            elif command == "monitor":
                fills = self.monitor_fills()
                return json.dumps({"fills": fills}, indent=2)

            else:
                return json.dumps({"error": f"Unknown command: {command}"})

        except json.JSONDecodeError:
            # Natural language - use LLM to process with prompt from YAML config
            try:
                agent_config = load_agent_config("agents")
                system_prompt = agent_config.get("executor_agent", {}).get(
                    "system_prompt",
                    "You are an execution agent. Return JSON responses.",
                )
            except Exception:
                system_prompt = "You are an execution agent. Return JSON responses."
            return self.process_with_tools(content, system_prompt)


def create_executor_agent(
    name: str = "executor_agent",
    initial_capital: float = 100000,
    **kwargs,
) -> ExecutorAgent:
    """Factory function to create a properly configured executor agent."""
    return ExecutorAgent(name=name, initial_capital=initial_capital, **kwargs)
