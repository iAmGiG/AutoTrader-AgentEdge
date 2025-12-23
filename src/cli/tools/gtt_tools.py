"""
GTT CLI Tools - FunctionTool wrappers for GTT triggers.

Issue #340: CLI integration for Good-Till-Triggered persistent triggers.

This module wraps the GTT module functions as FunctionTool instances
for integration with the AutoGen agent architecture.

Pattern: Pure function wrappers -> FunctionTool -> Registry
"""

import logging
from typing import Any, Dict, Optional

from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def _get_gtt_manager():
    """Get GTTManager instance."""
    try:
        from src.trading.gtt.gtt_manager import get_gtt_manager

        return get_gtt_manager()
    except Exception as e:
        logger.error(f"Failed to get GTT manager: {e}")
        return None


def _get_condition_type(condition_str: str):
    """Convert condition string to ConditionType enum."""
    from src.trading.gtt.gtt_manager import ConditionType

    mapping = {
        # Phase 1: Price-based
        "above": ConditionType.PRICE_ABOVE,
        "price_above": ConditionType.PRICE_ABOVE,
        "below": ConditionType.PRICE_BELOW,
        "price_below": ConditionType.PRICE_BELOW,
        "gain": ConditionType.PCT_GAIN,
        "pct_gain": ConditionType.PCT_GAIN,
        "loss": ConditionType.PCT_LOSS,
        "pct_loss": ConditionType.PCT_LOSS,
        "trailing": ConditionType.TRAILING_STOP,
        "trailing_stop": ConditionType.TRAILING_STOP,
        # Phase 2: Time-based
        "time": ConditionType.TIME_WINDOW,
        "time_window": ConditionType.TIME_WINDOW,
        # Phase 2: Volume-based
        "volume": ConditionType.VOLUME_ABOVE,
        "volume_above": ConditionType.VOLUME_ABOVE,
        "spike": ConditionType.VOLUME_SPIKE,
        "volume_spike": ConditionType.VOLUME_SPIKE,
    }
    return mapping.get(condition_str.lower())


def _get_action_type(action_str: str):
    """Convert action string to ActionType enum."""
    from src.trading.gtt.gtt_manager import ActionType

    mapping = {
        "alert": ActionType.ALERT,
        "order": ActionType.PLACE_ORDER,
        "place_order": ActionType.PLACE_ORDER,
        "cancel": ActionType.CANCEL_ORDER,
        "cancel_order": ActionType.CANCEL_ORDER,
    }
    return mapping.get(action_str.lower(), ActionType.ALERT)


# =============================================================================
# FunctionTool Wrapper Functions
# =============================================================================


def create_gtt_trigger(
    symbol: str,
    condition: str,
    value: float,
    action: str = "alert",
    expiration_days: Optional[int] = None,
    max_triggers: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new GTT (Good-Till-Triggered) trigger.

    GTT triggers persist across sessions and are checked twice daily
    (morning 9:20 AM and evening 3:50 PM ET).

    Args:
        symbol: Stock ticker symbol (e.g., "SPY", "AAPL")
        condition: Trigger condition - "above", "below", "gain", "loss", "trailing"
        value: Price or percentage that triggers the action
        action: Action to take - "alert" (default), "order"
        expiration_days: Days until trigger expires (None = no expiration)
        max_triggers: Max times to fire (None = unlimited, 1 = one-time)
        notes: Optional notes for the trigger

    Returns:
        Dict with status and trigger details

    Examples:
        - "Alert if SPY hits $620": condition="above", value=620
        - "Alert if AAPL drops to $180": condition="below", value=180
        - "Trailing stop 5%": condition="trailing", value=0.05
    """
    try:
        mgr = _get_gtt_manager()
        if not mgr:
            return {"status": "error", "message": "GTT manager not available"}

        condition_type = _get_condition_type(condition)
        if not condition_type:
            return {
                "status": "error",
                "message": f"Unknown condition: {condition}. Use: above, below, gain, loss, trailing",
            }

        action_type = _get_action_type(action)

        trigger = mgr.create_trigger(
            symbol=symbol,
            condition_type=condition_type,
            trigger_value=value,
            action_type=action_type,
            expiration_days=expiration_days,
            max_triggers=max_triggers,
            notes=notes,
        )

        if trigger:
            return {
                "status": "success",
                "trigger_id": trigger.id,
                "symbol": trigger.symbol,
                "condition": trigger.condition_type,
                "value": trigger.trigger_value,
                "action": trigger.action_type,
                "expiration": trigger.expiration_date,
                "max_triggers": trigger.max_triggers or "unlimited",
                "message": f"GTT trigger created: {trigger.symbol} {trigger.condition_type} @ {trigger.trigger_value}",
            }

        return {"status": "error", "message": "Failed to create trigger"}

    except Exception as e:
        logger.error(f"Error creating GTT trigger: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def create_gtt_oco_pair(
    symbol: str,
    condition_a: str,
    value_a: float,
    condition_b: str,
    value_b: float,
    expiration_days: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Create an OCO (One-Cancels-Other) trigger pair.

    When one trigger fires, both are automatically disabled.
    Useful for breakout/breakdown strategies.

    Args:
        symbol: Stock ticker symbol
        condition_a: First trigger condition (e.g., "above")
        value_a: First trigger value (e.g., 620 for $620)
        condition_b: Second trigger condition (e.g., "below")
        value_b: Second trigger value (e.g., 580 for $580)
        expiration_days: Days until triggers expire

    Returns:
        Dict with status and both trigger details

    Example:
        "Alert if SPY breaks above $620 or below $580":
        condition_a="above", value_a=620, condition_b="below", value_b=580
    """
    try:
        mgr = _get_gtt_manager()
        if not mgr:
            return {"status": "error", "message": "GTT manager not available"}

        cond_type_a = _get_condition_type(condition_a)
        cond_type_b = _get_condition_type(condition_b)

        if not cond_type_a or not cond_type_b:
            return {"status": "error", "message": "Invalid condition type"}

        trigger_a, trigger_b = mgr.create_oco_pair(
            symbol=symbol,
            condition_a=cond_type_a,
            value_a=value_a,
            condition_b=cond_type_b,
            value_b=value_b,
            expiration_days=expiration_days,
            notes_a=f"OCO: {condition_a} ${value_a}",
            notes_b=f"OCO: {condition_b} ${value_b}",
        )

        if trigger_a and trigger_b:
            return {
                "status": "success",
                "oco_group_id": trigger_a.oco_group_id,
                "trigger_a": {
                    "id": trigger_a.id,
                    "condition": trigger_a.condition_type,
                    "value": trigger_a.trigger_value,
                },
                "trigger_b": {
                    "id": trigger_b.id,
                    "condition": trigger_b.condition_type,
                    "value": trigger_b.trigger_value,
                },
                "message": f"OCO pair created: {symbol} {condition_a} ${value_a} OR {condition_b} ${value_b}",
            }

        return {"status": "error", "message": "Failed to create OCO pair"}

    except Exception as e:
        logger.error(f"Error creating OCO pair: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def list_gtt_triggers(
    symbol: Optional[str] = None,
    include_disabled: bool = False,
) -> Dict[str, Any]:
    """
    List GTT triggers.

    Args:
        symbol: Optional filter by symbol
        include_disabled: Include disabled triggers (default: False)

    Returns:
        Dict with status and list of triggers
    """
    try:
        mgr = _get_gtt_manager()
        if not mgr:
            return {"status": "error", "message": "GTT manager not available"}

        if symbol:
            triggers = mgr.get_triggers(
                symbol=symbol, enabled_only=not include_disabled, active_only=False
            )
        else:
            triggers = mgr.get_all_triggers(include_disabled=include_disabled)

        trigger_list = [t.to_dict() for t in triggers]

        return {
            "status": "success",
            "count": len(trigger_list),
            "triggers": trigger_list,
            "filter_symbol": symbol,
        }

    except Exception as e:
        logger.error(f"Error listing GTT triggers: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def delete_gtt_trigger(trigger_id: int) -> Dict[str, Any]:
    """
    Delete a GTT trigger.

    Args:
        trigger_id: ID of trigger to delete

    Returns:
        Dict with status
    """
    try:
        mgr = _get_gtt_manager()
        if not mgr:
            return {"status": "error", "message": "GTT manager not available"}

        # Get trigger info before deleting
        trigger = mgr.get_trigger(trigger_id)
        if not trigger:
            return {"status": "error", "message": f"Trigger {trigger_id} not found"}

        success = mgr.delete_trigger(trigger_id)

        if success:
            return {
                "status": "success",
                "message": f"Deleted GTT trigger {trigger_id} ({trigger.symbol} {trigger.condition_type})",
            }

        return {"status": "error", "message": f"Failed to delete trigger {trigger_id}"}

    except Exception as e:
        logger.error(f"Error deleting GTT trigger: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def disable_gtt_trigger(trigger_id: int) -> Dict[str, Any]:
    """
    Disable a GTT trigger (can be re-enabled later).

    Args:
        trigger_id: ID of trigger to disable

    Returns:
        Dict with status
    """
    try:
        mgr = _get_gtt_manager()
        if not mgr:
            return {"status": "error", "message": "GTT manager not available"}

        trigger = mgr.get_trigger(trigger_id)
        if not trigger:
            return {"status": "error", "message": f"Trigger {trigger_id} not found"}

        success = mgr.disable_trigger(trigger_id)

        if success:
            return {
                "status": "success",
                "message": f"Disabled GTT trigger {trigger_id} ({trigger.symbol} {trigger.condition_type})",
            }

        return {"status": "error", "message": f"Failed to disable trigger {trigger_id}"}

    except Exception as e:
        logger.error(f"Error disabling GTT trigger: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def enable_gtt_trigger(trigger_id: int) -> Dict[str, Any]:
    """
    Enable a previously disabled GTT trigger.

    Args:
        trigger_id: ID of trigger to enable

    Returns:
        Dict with status
    """
    try:
        mgr = _get_gtt_manager()
        if not mgr:
            return {"status": "error", "message": "GTT manager not available"}

        trigger = mgr.get_trigger(trigger_id)
        if not trigger:
            return {"status": "error", "message": f"Trigger {trigger_id} not found"}

        success = mgr.enable_trigger(trigger_id)

        if success:
            return {
                "status": "success",
                "message": f"Enabled GTT trigger {trigger_id} ({trigger.symbol} {trigger.condition_type})",
            }

        return {"status": "error", "message": f"Failed to enable trigger {trigger_id}"}

    except Exception as e:
        logger.error(f"Error enabling GTT trigger: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def get_gtt_summary() -> Dict[str, Any]:
    """
    Get summary of GTT triggers.

    Returns:
        Dict with status and summary statistics
    """
    try:
        mgr = _get_gtt_manager()
        if not mgr:
            return {"status": "error", "message": "GTT manager not available"}

        summary = mgr.get_summary()
        summary["status"] = "success"
        return summary

    except Exception as e:
        logger.error(f"Error getting GTT summary: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# =============================================================================
# Display Functions
# =============================================================================


def show_gtt_triggers(symbol: Optional[str] = None) -> str:  # noqa: C901
    """Display GTT triggers with formatted output."""
    result = list_gtt_triggers(symbol=symbol, include_disabled=True)

    if result["status"] == "error":
        return f"Error: {result.get('error', result.get('message', 'Unknown'))}"

    triggers = result.get("triggers", [])
    if not triggers:
        if symbol:
            return f"No GTT triggers for {symbol.upper()}"
        return "No GTT triggers. Use 'alert if SYMBOL hits PRICE' to create one."

    lines = [f"GTT Triggers ({len(triggers)})", "=" * 60]

    for t in triggers:
        # Status indicator
        if not t.get("enabled"):
            status = "DISABLED"
        elif t.get("is_expired"):
            status = "EXPIRED"
        elif not t.get("is_active"):
            status = "INACTIVE"
        else:
            status = "ACTIVE"

        # Build line
        line = f"[{t['id']}] {t['symbol']} {t['condition_type']} @ {t['trigger_value']}"
        lines.append(line)
        lines.append(f"     Action: {t['action_type']} | Status: {status}")

        # Additional info
        extras = []
        if t.get("expiration_date"):
            extras.append(f"Expires: {t['expiration_date'][:10]}")
        if t.get("max_triggers"):
            extras.append(f"Max: {t['max_triggers']} (fired: {t.get('trigger_count', 0)})")
        if t.get("oco_group_id"):
            extras.append(f"OCO Group: {t['oco_group_id']}")

        if extras:
            lines.append(f"     {' | '.join(extras)}")

        if t.get("notes"):
            lines.append(f"     Notes: {t['notes']}")

        lines.append("")

    return "\n".join(lines)


def show_gtt_summary() -> str:
    """Display GTT summary with formatted output."""
    result = get_gtt_summary()

    if result["status"] == "error":
        return f"Error: {result.get('error', result.get('message', 'Unknown'))}"

    lines = [
        "GTT Summary",
        "=" * 40,
        f"  Total triggers: {result.get('total_triggers', 0)}",
        f"  Active triggers: {result.get('active_triggers', 0)}",
        f"  Expired triggers: {result.get('expired_triggers', 0)}",
        f"  Symbols monitored: {result.get('symbols_monitored', 0)}",
        f"  OCO groups: {result.get('oco_groups', 0)}",
    ]

    return "\n".join(lines)


# =============================================================================
# FunctionTool Registration
# =============================================================================


create_gtt_trigger_tool = FunctionTool(
    func=create_gtt_trigger,
    name="create_gtt_trigger",
    description=(
        "Create a GTT (Good-Till-Triggered) persistent price trigger. "
        "Triggers are checked twice daily and can alert or place orders "
        "when conditions are met. Supports: above, below, gain, loss, trailing."
    ),
)

create_gtt_oco_tool = FunctionTool(
    func=create_gtt_oco_pair,
    name="create_gtt_oco_pair",
    description=(
        "Create an OCO (One-Cancels-Other) trigger pair. "
        "When one trigger fires, both are disabled. "
        "Useful for breakout/breakdown strategies."
    ),
)

list_gtt_triggers_tool = FunctionTool(
    func=list_gtt_triggers,
    name="list_gtt_triggers",
    description="List GTT triggers, optionally filtered by symbol.",
)

delete_gtt_trigger_tool = FunctionTool(
    func=delete_gtt_trigger,
    name="delete_gtt_trigger",
    description="Delete a GTT trigger by ID.",
)

disable_gtt_trigger_tool = FunctionTool(
    func=disable_gtt_trigger,
    name="disable_gtt_trigger",
    description="Disable a GTT trigger (can be re-enabled later).",
)

enable_gtt_trigger_tool = FunctionTool(
    func=enable_gtt_trigger,
    name="enable_gtt_trigger",
    description="Enable a previously disabled GTT trigger.",
)

show_gtt_triggers_tool = FunctionTool(
    func=show_gtt_triggers,
    name="show_gtt_triggers",
    description="Display GTT triggers with formatted output.",
)

show_gtt_summary_tool = FunctionTool(
    func=show_gtt_summary,
    name="show_gtt_summary",
    description="Display summary of GTT triggers.",
)


# =============================================================================
# Export
# =============================================================================


CLI_GTT_TOOLS = [
    create_gtt_trigger_tool,
    create_gtt_oco_tool,
    list_gtt_triggers_tool,
    delete_gtt_trigger_tool,
    disable_gtt_trigger_tool,
    enable_gtt_trigger_tool,
    show_gtt_triggers_tool,
    show_gtt_summary_tool,
]


__all__ = [
    # Functions
    "create_gtt_trigger",
    "create_gtt_oco_pair",
    "list_gtt_triggers",
    "delete_gtt_trigger",
    "disable_gtt_trigger",
    "enable_gtt_trigger",
    "show_gtt_triggers",
    "show_gtt_summary",
    # Tools
    "CLI_GTT_TOOLS",
    "create_gtt_trigger_tool",
    "create_gtt_oco_tool",
    "list_gtt_triggers_tool",
    "delete_gtt_trigger_tool",
    "disable_gtt_trigger_tool",
    "enable_gtt_trigger_tool",
    "show_gtt_triggers_tool",
    "show_gtt_summary_tool",
]
