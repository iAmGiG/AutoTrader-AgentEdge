"""
Partial Exit CLI Tools - FunctionTool wrappers for partial exit management.

Issue #508: CLI integration for multi-target position exits.

This module wraps the PartialExitManager functions as FunctionTool instances
for integration with the AutoGen agent architecture and CLI.

Pattern: Pure function wrappers -> FunctionTool -> Registry
"""

import logging

from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def _get_partial_exit_manager():
    """Get PartialExitManager instance."""
    try:
        from src.trading.orders.partial_exit_manager import PartialExitManager

        return PartialExitManager()
    except Exception as e:
        logger.error(f"Failed to get PartialExitManager: {e}")
        return None


# =============================================================================
# FunctionTool Wrapper Functions
# =============================================================================


def show_all_partial_exits() -> str:
    """
    Show all registered partial exit plans.

    Returns:
        Formatted string with all partial exit positions

    Example:
        >>> show_all_partial_exits()
        'Partial Exit Plans
        AAPL: 100 shares @ $150.00 entry
          Target 1: 50 shares (limit @ $156.00)
          Target 2: 50 shares (trailing stop)'
    """
    manager = _get_partial_exit_manager()
    if not manager:
        return "[ERROR] Could not access PartialExitManager"

    try:
        # Get all positions from manager's state
        if not hasattr(manager, "positions") or not manager.positions:
            return "[INFO] No partial exit plans registered.\n\nUse order manager to set up partial exits."

        output = "Partial Exit Plans\n"
        output += "=" * 60 + "\n\n"

        for symbol, state in manager.positions.items():
            output += f"[{symbol}] {state.total_quantity} shares @ ${state.entry_price:.2f}\n"
            output += f"  Registered: {state.registered_at}\n"
            output += f"  Remaining: {state.get_remaining_quantity()} shares\n\n"

            output += "  Targets:\n"
            for target in state.targets:
                status = "[FILLED]" if target.filled else "[ACTIVE]"
                output += f"    {status} Target {target.target_number}: {target.quantity} shares\n"
                if target.exit_type == "limit":
                    output += f"              Type: Limit @ ${target.exit_price:.2f}\n"
                else:
                    output += "              Type: Trailing Stop\n"
                if target.filled_at:
                    output += f"              Filled: {target.filled_at}\n"
                output += "\n"

            output += f"  Stop Price: ${state.stop_price:.2f}\n"
            output += "-" * 60 + "\n\n"

        return output

    except Exception as e:
        logger.error(f"Error showing partial exits: {e}")
        return f"[ERROR] Failed to retrieve partial exits: {e}"


def show_partial_exit_plan(symbol: str) -> str:
    """
    Show partial exit plan for a specific symbol.

    Args:
        symbol: Trading symbol (e.g., 'AAPL')

    Returns:
        Formatted string with exit plan details

    Example:
        >>> show_partial_exit_plan('AAPL')
        'Partial Exit Plan: AAPL
        Position: 100 shares @ $150.00
        Remaining: 75 shares
        ...'
    """
    manager = _get_partial_exit_manager()
    if not manager:
        return "[ERROR] Could not access PartialExitManager"

    symbol = symbol.upper()

    try:
        state = manager.get_position_summary(symbol)
        if not state:
            return f"[INFO] No partial exit plan for {symbol}"

        # Format as readable string
        if isinstance(state, dict):
            output = f"Partial Exit Plan: {symbol}\n"
            output += "=" * 50 + "\n"
            output += f"Entry Price: ${state.get('entry_price', 'N/A')}\n"
            output += f"Total Quantity: {state.get('total_quantity', 'N/A')} shares\n"
            output += f"Remaining: {state.get('remaining_quantity', 'N/A')} shares\n"
            output += f"Stop Price: ${state.get('stop_price', 'N/A')}\n\n"
            output += "Targets:\n"

            targets = state.get("targets", [])
            for target in targets:
                status = "[FILLED]" if target.get("filled") else "[ACTIVE]"
                output += f"  {status} Target {target.get('target_number')}: {target.get('quantity')} shares\n"
                if target.get("exit_type") == "limit":
                    output += f"         Limit @ ${target.get('exit_price')}\n"
                else:
                    output += "         Trailing Stop\n"

            return output
        else:
            return str(state)

    except Exception as e:
        logger.error(f"Error showing partial exit plan for {symbol}: {e}")
        return f"[ERROR] Failed to retrieve exit plan for {symbol}: {e}"


def show_exit_targets(symbol: str) -> str:
    """
    Show exit target levels for a position.

    Args:
        symbol: Trading symbol

    Returns:
        Formatted string with target levels

    Example:
        >>> show_exit_targets('AAPL')
        'Exit Targets: AAPL
        Target 1: 50 shares @ limit $156.00 (4% gain)
        Target 2: 50 shares @ trailing stop'
    """
    manager = _get_partial_exit_manager()
    if not manager:
        return "[ERROR] Could not access PartialExitManager"

    symbol = symbol.upper()

    try:
        state = manager.get_position_summary(symbol)
        if not state:
            return f"[INFO] No targets configured for {symbol}"

        if isinstance(state, dict):
            output = f"Exit Targets: {symbol}\n"
            output += "=" * 50 + "\n"

            entry_price = state.get("entry_price", 0)
            targets = state.get("targets", [])

            for target in targets:
                target_num = target.get("target_number")
                quantity = target.get("quantity")
                exit_type = target.get("exit_type")
                exit_price = target.get("exit_price")
                filled = target.get("filled", False)

                status = "[FILLED]" if filled else "[ACTIVE]"
                output += f"{status} Target {target_num}: {quantity} shares\n"

                if exit_type == "limit" and exit_price:
                    gain_pct = (
                        ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
                    )
                    output += f"         @ Limit ${exit_price:.2f} ({gain_pct:+.1f}% gain)\n"
                else:
                    output += "         @ Trailing Stop\n"

            return output
        else:
            return str(state)

    except Exception as e:
        logger.error(f"Error showing targets for {symbol}: {e}")
        return f"[ERROR] Failed to retrieve targets for {symbol}: {e}"


def list_active_exits() -> str:
    """
    List only active (unfilled) exit targets.

    Returns:
        Formatted string with active targets

    Example:
        >>> list_active_exits()
        'Active Exit Targets
        AAPL: 2 targets, 75 shares remaining
        MSFT: 1 target, 100 shares remaining'
    """
    manager = _get_partial_exit_manager()
    if not manager:
        return "[ERROR] Could not access PartialExitManager"

    try:
        if not hasattr(manager, "positions") or not manager.positions:
            return "[INFO] No active exit targets."

        output = "Active Exit Targets\n"
        output += "=" * 60 + "\n\n"

        has_active = False
        for symbol, state in manager.positions.items():
            active_targets = state.get_active_targets()
            if active_targets:
                has_active = True
                remaining = state.get_remaining_quantity()
                output += (
                    f"[{symbol}] {len(active_targets)} target(s), {remaining} shares remaining\n"
                )

                for target in active_targets:
                    if target.exit_type == "limit":
                        output += f"  - Target {target.target_number}: {target.quantity}sh @ ${target.exit_price:.2f}\n"
                    else:
                        output += f"  - Target {target.target_number}: {target.quantity}sh @ Trailing Stop\n"

                output += "\n"

        if not has_active:
            output = (
                "[INFO] No active exit targets.\n\nAll targets have been filled or no plans exist."
            )

        return output

    except Exception as e:
        logger.error(f"Error listing active exits: {e}")
        return f"[ERROR] Failed to list active exits: {e}"


def get_exit_summary() -> str:
    """
    Get summary of all partial exit positions.

    Returns:
        Summary statistics

    Example:
        >>> get_exit_summary()
        'Partial Exit Summary
        Total Positions: 3
        Active Targets: 5
        Filled Targets: 2'
    """
    manager = _get_partial_exit_manager()
    if not manager:
        return "[ERROR] Could not access PartialExitManager"

    try:
        if not hasattr(manager, "positions") or not manager.positions:
            return "[INFO] No partial exit positions registered."

        total_positions = len(manager.positions)
        total_active = 0
        total_filled = 0
        total_remaining_qty = 0

        for symbol, state in manager.positions.items():
            total_active += len(state.get_active_targets())
            total_filled += len(state.get_filled_targets())
            total_remaining_qty += state.get_remaining_quantity()

        output = "Partial Exit Summary\n"
        output += "=" * 50 + "\n"
        output += f"Total Positions: {total_positions}\n"
        output += f"Active Targets: {total_active}\n"
        output += f"Filled Targets: {total_filled}\n"
        output += f"Shares Remaining: {total_remaining_qty}\n"

        return output

    except Exception as e:
        logger.error(f"Error generating exit summary: {e}")
        return f"[ERROR] Failed to generate summary: {e}"


def modify_exit_target(symbol: str, target_number: int, new_price: float) -> str:
    """
    Modify the exit price of a partial exit target.

    Updates the exit price for a specific target on a position.
    Only works for limit order targets that haven't been filled yet.

    Args:
        symbol: Stock ticker symbol (e.g., "AAPL")
        target_number: Target number to modify (1, 2, etc.)
        new_price: New exit price

    Returns:
        Success or error message

    Example:
        >>> modify_exit_target("AAPL", 1, 205.50)
        '[OK] Modified AAPL target 1: new exit price $205.50'
    """
    manager = _get_partial_exit_manager()
    if not manager:
        return "[ERROR] Could not access PartialExitManager"

    try:
        symbol = symbol.upper()

        if not hasattr(manager, "positions") or symbol not in manager.positions:
            return f"[ERROR] No partial exit plan found for {symbol}"

        state = manager.positions[symbol]

        # Find the target
        target = None
        for t in state.targets:
            if t.target_number == target_number:
                target = t
                break

        if not target:
            return f"[ERROR] Target {target_number} not found for {symbol}"

        if target.filled:
            return f"[ERROR] Target {target_number} for {symbol} has already been filled"

        if target.exit_type != "limit":
            return (
                f"[ERROR] Target {target_number} is a {target.exit_type} order, not a limit order"
            )

        old_price = target.exit_price
        target.exit_price = new_price

        # Update timestamp
        from src.utils.date_utils import now_iso

        state.last_updated = now_iso()

        return (
            f"[OK] Modified {symbol} target {target_number}\n"
            f"  Previous price: ${old_price:.2f}\n"
            f"  New price: ${new_price:.2f}"
        )

    except Exception as e:
        logger.error(f"Error modifying exit target: {e}")
        return f"[ERROR] Failed to modify target: {e}"


# =============================================================================
# FunctionTool Definitions
# =============================================================================

show_all_partial_exits_tool = FunctionTool(
    show_all_partial_exits,
    description=("Show all registered partial exit plans with target details."),
)

show_partial_exit_plan_tool = FunctionTool(
    show_partial_exit_plan,
    description=("Show partial exit plan for a specific symbol with all target details."),
)

show_exit_targets_tool = FunctionTool(
    show_exit_targets,
    description=("Show exit target levels and types for a position."),
)

list_active_exits_tool = FunctionTool(
    list_active_exits,
    description=("List only active (unfilled) exit targets across all positions."),
)

get_exit_summary_tool = FunctionTool(
    get_exit_summary,
    description=("Get summary statistics of all partial exit positions."),
)

modify_exit_target_tool = FunctionTool(
    modify_exit_target,
    description=("Modify the exit price of a partial exit target."),
)


# =============================================================================
# Tool Collection for Registry
# =============================================================================

CLI_PARTIAL_EXIT_TOOLS = [
    show_all_partial_exits_tool,
    show_partial_exit_plan_tool,
    show_exit_targets_tool,
    list_active_exits_tool,
    get_exit_summary_tool,
    modify_exit_target_tool,
]

__all__ = [
    # Functions
    "show_all_partial_exits",
    "show_partial_exit_plan",
    "show_exit_targets",
    "list_active_exits",
    "get_exit_summary",
    "modify_exit_target",
    # Tools
    "show_all_partial_exits_tool",
    "show_partial_exit_plan_tool",
    "show_exit_targets_tool",
    "list_active_exits_tool",
    "get_exit_summary_tool",
    "modify_exit_target_tool",
    # Collection
    "CLI_PARTIAL_EXIT_TOOLS",
]
