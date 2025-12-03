"""
Order Display Tools - FunctionTool wrappers for order management.

Issue #433/#458: Extract order display commands from cli_session.py.

These tools handle:
- Listing open/pending orders
- Viewing order details for specific symbols
- Order cancellation (all, by ID, by symbol)

Note: These are display/query tools. Actual order placement is handled by
the trading orchestrator and execution manager.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def _load_local_state() -> Dict[str, Any]:
    """
    Load local state from cost_efficient_positions.json.

    Returns:
        Dict with positions data or empty dict if not found
    """
    state_file = Path("state/cost_efficient_positions.json")
    if state_file.exists():
        try:
            with open(state_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load local state: {e}")
    return {}


def _get_account_monitor():
    """
    Get AlpacaAccountMonitor instance.

    Returns singleton or creates new instance.
    """
    try:
        from src.trading.trading_cycle import CostEfficientTradeCycle

        cycle = CostEfficientTradeCycle()
        return cycle.account_monitor
    except Exception as e:
        logger.error(f"Failed to get account monitor: {e}")
        return None


def _get_orchestrator():
    """
    Get TradingOrchestrator instance for order execution.

    Returns singleton or creates new instance.
    """
    try:
        from src.autogen_agents.trading_orchestrator import TradingOrchestrator

        return TradingOrchestrator()
    except Exception as e:
        logger.error(f"Failed to get orchestrator: {e}")
        return None


def _normalize_order(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize order data from API response.

    Args:
        order: Raw order dict from Alpaca API

    Returns:
        Normalized order dict with consistent field names
    """
    # Extract side
    side = order.get("side", "unknown")
    if hasattr(side, "value"):
        side = side.value

    # Extract order type
    order_type = order.get("type", order.get("order_type", "unknown"))
    if hasattr(order_type, "value"):
        order_type = order_type.value

    # Extract price based on order type
    if order_type == "limit":
        price = float(order.get("limit_price", 0) or 0)
    elif order_type == "stop":
        price = float(order.get("stop_price", 0) or 0)
    elif order_type == "stop_limit":
        price = float(order.get("stop_price", 0) or 0)
    else:
        price = float(order.get("filled_avg_price", 0) or 0)

    # Extract status
    status = order.get("status", "unknown")
    if hasattr(status, "value"):
        status = status.value

    return {
        "id": str(order.get("id", "")),
        "symbol": order.get("symbol", ""),
        "side": side,
        "type": order_type,
        "price": price,
        "qty": float(order.get("qty", 0) or 0),
        "filled_qty": float(order.get("filled_qty", 0) or 0),
        "status": status,
        "submitted_at": str(order.get("submitted_at", "")),
        "order_class": str(order.get("order_class", "simple")),
    }


# =============================================================================
# FunctionTool Wrapper Functions
# =============================================================================


def list_orders(
    status: str = "open", symbol: Optional[str] = None, include_local_state: bool = True
) -> Dict[str, Any]:
    """
    List orders with optional filtering.

    Args:
        status: Order status filter ("open", "closed", "all")
        symbol: Optional symbol to filter by
        include_local_state: Include local stop/target data

    Returns:
        Dict with:
        - status: "success" or "error"
        - orders: List of normalized order dicts
        - count: Total order count
        - by_symbol: Orders grouped by symbol
    """
    try:
        account_monitor = _get_account_monitor()
        if not account_monitor:
            return {"status": "error", "error": "Account monitor not available", "orders": []}

        # Get orders from broker
        orders = account_monitor.get_orders(status=status)
        if not orders:
            return {"status": "success", "orders": [], "count": 0, "by_symbol": {}}

        # Normalize orders
        normalized = [_normalize_order(o) for o in orders]

        # Filter by symbol if specified
        if symbol:
            symbol_upper = symbol.upper()
            normalized = [o for o in normalized if o["symbol"] == symbol_upper]

        # Group by symbol
        by_symbol: Dict[str, List[Dict]] = {}
        for order in normalized:
            sym = order["symbol"]
            if sym not in by_symbol:
                by_symbol[sym] = []
            by_symbol[sym].append(order)

        # Merge local state if requested
        local_state = {}
        if include_local_state:
            state = _load_local_state()
            local_state = state.get("positions", {})

        return {
            "status": "success",
            "orders": normalized,
            "count": len(normalized),
            "by_symbol": by_symbol,
            "local_state": local_state,
        }

    except Exception as e:
        logger.error(f"Error listing orders: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "orders": []}


def get_position_orders(ticker: str) -> Dict[str, Any]:
    """
    Get detailed orders for a specific position/ticker.

    Shows entry orders, stop orders, and target orders for the symbol.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with:
        - status: "success", "no_orders", or "error"
        - ticker: The requested ticker
        - entry_orders: Filled entry orders (most recent)
        - open_orders: Currently open orders for this symbol
        - local_state: Stop/target from local state file
    """
    try:
        account_monitor = _get_account_monitor()
        if not account_monitor:
            return {"status": "error", "error": "Account monitor not available"}

        ticker_upper = ticker.upper()

        # Get all orders for analysis
        all_orders = account_monitor.get_orders(status="all")
        symbol_orders = [o for o in all_orders if o.get("symbol") == ticker_upper]

        if not symbol_orders:
            return {
                "status": "no_orders",
                "ticker": ticker_upper,
                "message": f"No orders found for {ticker_upper}",
            }

        # Separate by status
        entry_orders = []
        open_orders = []

        for order in symbol_orders:
            normalized = _normalize_order(order)
            status = normalized["status"]

            if status == "filled":
                entry_orders.append(normalized)
            elif status in ("new", "accepted", "pending_new", "partially_filled"):
                open_orders.append(normalized)

        # Sort entry orders by date (most recent first), limit to 3
        entry_orders.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)
        entry_orders = entry_orders[:3]

        # Get local state for this ticker
        local_state = _load_local_state()
        ticker_state = local_state.get("positions", {}).get(ticker_upper, {})

        return {
            "status": "success",
            "ticker": ticker_upper,
            "entry_orders": entry_orders,
            "open_orders": open_orders,
            "local_state": ticker_state,
        }

    except Exception as e:
        logger.error(f"Error getting position orders for {ticker}: {e}", exc_info=True)
        return {"status": "error", "ticker": ticker, "error": str(e)}


def cancel_order(order_id: str) -> Dict[str, Any]:
    """
    Cancel a specific order by ID.

    Args:
        order_id: Order ID (full or partial match)

    Returns:
        Dict with:
        - status: "success", "not_found", or "error"
        - order_id: The matched order ID
        - cancelled: True if successfully cancelled
    """
    try:
        orchestrator = _get_orchestrator()
        if not orchestrator or not hasattr(orchestrator, "executor"):
            return {"status": "error", "error": "Orchestrator/executor not available"}

        account_monitor = _get_account_monitor()
        if not account_monitor:
            return {"status": "error", "error": "Account monitor not available"}

        # Find matching order
        open_orders = account_monitor.get_orders(status="open")
        matching = [o for o in open_orders if str(o.get("id", "")).startswith(order_id)]

        if not matching:
            return {
                "status": "not_found",
                "order_id": order_id,
                "message": f"No open order found matching '{order_id}'",
            }

        if len(matching) > 1:
            return {
                "status": "ambiguous",
                "order_id": order_id,
                "matches": [str(o.get("id")) for o in matching],
                "message": f"Multiple orders match '{order_id}', please be more specific",
            }

        # Cancel the order
        order = matching[0]
        full_id = str(order.get("id"))
        result = orchestrator.executor.cancel_order(full_id)

        if result.get("status") == "success":
            return {
                "status": "success",
                "order_id": full_id,
                "cancelled": True,
                "symbol": order.get("symbol"),
            }
        else:
            return {
                "status": "error",
                "order_id": full_id,
                "cancelled": False,
                "error": result.get("error", "Unknown error"),
            }

    except Exception as e:
        logger.error(f"Error cancelling order {order_id}: {e}", exc_info=True)
        return {"status": "error", "order_id": order_id, "error": str(e)}


def cancel_all_orders() -> Dict[str, Any]:
    """
    Cancel all open orders.

    Returns:
        Dict with:
        - status: "success" or "error"
        - cancelled_count: Number of orders cancelled
        - failed_count: Number of cancellations that failed
        - results: List of individual cancellation results
    """
    try:
        orchestrator = _get_orchestrator()
        if not orchestrator or not hasattr(orchestrator, "executor"):
            return {"status": "error", "error": "Orchestrator/executor not available"}

        account_monitor = _get_account_monitor()
        if not account_monitor:
            return {"status": "error", "error": "Account monitor not available"}

        open_orders = account_monitor.get_orders(status="open")
        if not open_orders:
            return {
                "status": "success",
                "cancelled_count": 0,
                "failed_count": 0,
                "message": "No open orders to cancel",
            }

        results = []
        cancelled = 0
        failed = 0

        for order in open_orders:
            order_id = str(order.get("id"))
            try:
                result = orchestrator.executor.cancel_order(order_id)
                if result.get("status") == "success":
                    cancelled += 1
                    results.append({"order_id": order_id, "status": "cancelled"})
                else:
                    failed += 1
                    results.append(
                        {"order_id": order_id, "status": "failed", "error": result.get("error")}
                    )
            except Exception as e:
                failed += 1
                results.append({"order_id": order_id, "status": "failed", "error": str(e)})

        return {
            "status": "success",
            "cancelled_count": cancelled,
            "failed_count": failed,
            "total_orders": len(open_orders),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error cancelling all orders: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def cancel_symbol_orders(symbol: str) -> Dict[str, Any]:
    """
    Cancel all open orders for a specific symbol.

    Args:
        symbol: Stock ticker symbol

    Returns:
        Dict with:
        - status: "success" or "error"
        - symbol: The symbol
        - cancelled_count: Number of orders cancelled
        - failed_count: Number of cancellations that failed
    """
    try:
        orchestrator = _get_orchestrator()
        if not orchestrator or not hasattr(orchestrator, "executor"):
            return {"status": "error", "error": "Orchestrator/executor not available"}

        account_monitor = _get_account_monitor()
        if not account_monitor:
            return {"status": "error", "error": "Account monitor not available"}

        symbol_upper = symbol.upper()
        open_orders = account_monitor.get_orders(status="open")
        symbol_orders = [o for o in open_orders if o.get("symbol") == symbol_upper]

        if not symbol_orders:
            return {
                "status": "success",
                "symbol": symbol_upper,
                "cancelled_count": 0,
                "message": f"No open orders for {symbol_upper}",
            }

        cancelled = 0
        failed = 0

        for order in symbol_orders:
            order_id = str(order.get("id"))
            try:
                result = orchestrator.executor.cancel_order(order_id)
                if result.get("status") == "success":
                    cancelled += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return {
            "status": "success",
            "symbol": symbol_upper,
            "cancelled_count": cancelled,
            "failed_count": failed,
            "total_orders": len(symbol_orders),
        }

    except Exception as e:
        logger.error(f"Error cancelling orders for {symbol}: {e}", exc_info=True)
        return {"status": "error", "symbol": symbol, "error": str(e)}


# =============================================================================
# Display Functions (Issue #459 - formatted output for CLI)
# =============================================================================


def show_orders() -> str:
    """Display all open orders with hierarchical formatting."""
    result = list_orders(status="open", include_local_state=True)
    if result["status"] == "error":
        return f"❌ Error: {result.get('error', 'Unknown')}"
    if result["count"] == 0:
        return "ℹ️  No open orders"

    lines = [f"📋 Open Orders ({result['count']} total)", ""]
    by_symbol = result.get("by_symbol", {})
    local_state = result.get("local_state", {})
    has_local = False

    for symbol, orders in by_symbol.items():
        if not orders:
            continue
        first_side = orders[0].get("side", "buy")
        direction = "LONG" if first_side == "buy" else "SHORT"
        symbol_local = local_state.get(symbol, {})
        local_orders = []
        if symbol_local.get("stop_price"):
            local_orders.append(
                {
                    "side": "sell" if direction == "LONG" else "buy",
                    "type": "stop",
                    "price": symbol_local["stop_price"],
                    "qty": symbol_local.get("quantity", 0),
                    "id": "local-stop",
                }
            )
            has_local = True
        all_orders = orders + local_orders
        lines.append(f"┌─ ${symbol} ({len(all_orders)} orders) - {direction}")
        stops = [o for o in all_orders if o.get("type") == "stop"]
        limits = [o for o in all_orders if o.get("type") == "limit"]
        others = [o for o in all_orders if o.get("type") not in ("stop", "limit")]
        for i, order in enumerate(limits):
            conn = "└─" if i == len(limits) - 1 and not stops and not others else "├─"
            local_mark = " *" if str(order.get("id", "")).startswith("local") else ""
            lines.append(
                f"│ {conn} 🎯 PT: {order['side']} {order.get('qty', 0)} @ ${order.get('price', 0):.2f}{local_mark}"
            )
        for i, order in enumerate(stops):
            conn = "└─" if i == len(stops) - 1 and not others else "├─"
            local_mark = " *" if str(order.get("id", "")).startswith("local") else ""
            lines.append(
                f"│ {conn} 🛑 SL: {order['side']} {order.get('qty', 0)} @ ${order.get('price', 0):.2f}{local_mark}"
            )
        for i, order in enumerate(others):
            conn = "└─" if i == len(others) - 1 else "├─"
            lines.append(
                f"│ {conn} 📌 {order['side']} {order.get('qty', 0)} @ ${order.get('price', 0):.2f}"
            )
        lines.append("")
    if has_local:
        lines.extend(["─" * 50, "* Orders marked with * are from local state"])
    return "\n".join(lines)


def show_position_orders(ticker: str) -> str:
    """Display detailed orders for a specific position."""
    result = get_position_orders(ticker)
    if result["status"] == "error":
        return f"❌ Error: {result.get('error', 'Unknown')}"
    if result["status"] == "no_orders":
        return f"ℹ️  No orders found for {result['ticker']}"
    lines = [f"📋 {result['ticker']} Orders", ""]
    entry_orders = result.get("entry_orders", [])
    if entry_orders:
        lines.append("✅ ENTRY (Filled)")
        for order in entry_orders[:3]:
            lines.append(
                f"   {order.get('side', '?').upper()} {order.get('qty', 0)} @ ${order.get('price', 0):.2f}"
            )
    open_orders = result.get("open_orders", [])
    if open_orders:
        lines.extend(["", "🟡 OPEN Exit Orders"])
        for order in open_orders:
            otype = order.get("type", "unknown")
            price = order.get("price", 0)
            emoji = "🔴" if otype == "stop" else "🟢" if otype == "limit" else "📌"
            label = (
                "STOP LOSS"
                if otype == "stop"
                else "TAKE PROFIT" if otype == "limit" else otype.upper()
            )
            lines.append(f"   {emoji} {label}: ${price:.2f}")
    local_state = result.get("local_state", {})
    if local_state.get("stop_price") or local_state.get("target_price"):
        if not open_orders:
            lines.extend(["", "🟡 Exit Orders (from local state)"])
        if local_state.get("stop_price"):
            lines.extend(
                [f"   🔴 STOP LOSS: ${local_state['stop_price']:.2f}", "      * Verify on broker"]
            )
        if local_state.get("target_price"):
            lines.extend(
                [
                    f"   🟢 TAKE PROFIT: ${local_state['target_price']:.2f}",
                    "      * Verify on broker",
                ]
            )
    return "\n".join(lines)


# =============================================================================
# FunctionTool Registration
# =============================================================================


show_orders_tool = FunctionTool(
    func=show_orders,
    name="show_orders",
    description="Display all open orders with hierarchical formatting.",
)

show_position_orders_tool = FunctionTool(
    func=show_position_orders,
    name="show_position_orders",
    description="Display detailed orders for a specific ticker.",
)

list_orders_tool = FunctionTool(
    func=list_orders,
    name="list_orders",
    description="List open, closed, or all orders with optional symbol filtering.",
)

get_position_orders_tool = FunctionTool(
    func=get_position_orders,
    name="get_position_orders",
    description="Get detailed orders for a specific ticker including entry, stop, and target orders.",
)

cancel_order_tool = FunctionTool(
    func=cancel_order,
    name="cancel_order",
    description="Cancel a specific order by ID (supports partial ID matching).",
)

cancel_all_orders_tool = FunctionTool(
    func=cancel_all_orders,
    name="cancel_all_orders",
    description="Cancel all open orders across all symbols.",
)

cancel_symbol_orders_tool = FunctionTool(
    func=cancel_symbol_orders,
    name="cancel_symbol_orders",
    description="Cancel all open orders for a specific symbol.",
)


# Export list for CLI tools registry
CLI_ORDER_TOOLS = [
    show_orders_tool,
    show_position_orders_tool,
    list_orders_tool,
    get_position_orders_tool,
    cancel_order_tool,
    cancel_all_orders_tool,
    cancel_symbol_orders_tool,
]

__all__ = [
    # Display Functions
    "show_orders",
    "show_position_orders",
    # Data Functions
    "list_orders",
    "get_position_orders",
    "cancel_order",
    "cancel_all_orders",
    "cancel_symbol_orders",
    # FunctionTools
    "CLI_ORDER_TOOLS",
    "show_orders_tool",
    "show_position_orders_tool",
    "list_orders_tool",
    "get_position_orders_tool",
    "cancel_order_tool",
    "cancel_all_orders_tool",
    "cancel_symbol_orders_tool",
]
