"""
Execution Mode CLI Tools - FunctionTool wrappers for execution mode management.

Issue #436: Extract execution mode tools from cli_session.py.
Issue #332: Execution mode switching commands (already implemented in cli_session).

This module wraps execution mode management as FunctionTool instances
for integration with the AutoGen agent architecture.

Execution Modes:
- CONFIRM: Requires human approval for each trade (default)
- AUTO: Executes trades automatically (within risk limits)
- PAPER: Paper trading only, no real money
- DISABLED: Trading completely disabled
"""

import logging
from typing import Any, Dict

from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)

# Category constant for execution mode tools
EXECUTION_MODE_TOOLS = "execution_mode"

# ============================================================================
# Module-level orchestrator reference
# ============================================================================
# This will be set by cli_session when it initializes

_orchestrator = None


def set_orchestrator(orchestrator) -> None:
    """
    Set the orchestrator reference for execution mode tools.

    Called by CLISession.__init__ to provide access to the orchestrator.

    Args:
        orchestrator: TradingOrchestrator instance
    """
    global _orchestrator
    _orchestrator = orchestrator
    logger.debug("Execution mode tools: orchestrator set")


def _get_orchestrator():
    """Get the orchestrator instance."""
    if _orchestrator is None:
        raise RuntimeError("Orchestrator not set. Call set_orchestrator() first.")
    return _orchestrator


# ============================================================================
# Pure Function Wrappers
# ============================================================================


def show_execution_mode() -> str:
    """
    Show the current execution mode with descriptions.

    Displays the active execution mode and explains all available modes.

    Returns:
        Formatted string showing current mode and all options

    Example:
        >>> show_execution_mode()
        '\\n📋 Current Execution Mode: CONFIRM\\n...'
    """
    try:
        orchestrator = _get_orchestrator()
        current_mode = orchestrator.execution_mode

        lines = [
            f"\n📋 Current Execution Mode: {current_mode.value.upper()}",
            "",
            "Mode Descriptions:",
            "  • CONFIRM  - Requires human approval for each trade",
            "  • AUTO     - Executes trades automatically (within risk limits)",
            "  • PAPER    - Paper trading only, no real money",
            "  • DISABLED - Trading completely disabled",
            "",
            "To change mode: set execution mode {confirm|auto|paper|disabled}",
        ]
        return "\n".join(lines)

    except RuntimeError:
        return "❌ Execution mode tools not initialized"
    except Exception as e:
        logger.error(f"Error showing execution mode: {e}")
        return f"❌ Error: {e}"


def set_execution_mode(mode: str) -> Dict[str, Any]:
    """
    Set the execution mode (without confirmation prompts).

    This is a data function that returns a result dict.
    The CLI handler should manage confirmation prompts for AUTO mode.

    Args:
        mode: Target mode ('confirm', 'auto', 'paper', 'disabled')

    Returns:
        Dict with status, old_mode, new_mode, and any messages

    Example:
        >>> set_execution_mode('paper')
        {'status': 'success', 'old_mode': 'confirm', 'new_mode': 'paper'}
    """
    try:
        from src.autogen_agents import ExecutionMode

        orchestrator = _get_orchestrator()
        target_mode = mode.lower().strip()

        # Validate mode
        valid_modes = ["confirm", "auto", "paper", "disabled"]
        if target_mode not in valid_modes:
            return {
                "status": "error",
                "error": f"Invalid mode: {target_mode}",
                "valid_modes": valid_modes,
            }

        new_mode = ExecutionMode(target_mode)
        old_mode = orchestrator.execution_mode

        # Check if switching to AUTO (requires confirmation from caller)
        if new_mode == ExecutionMode.AUTO and old_mode != ExecutionMode.AUTO:
            return {
                "status": "requires_confirmation",
                "old_mode": old_mode.value,
                "new_mode": new_mode.value,
                "warning": "AUTO mode executes trades without confirmation",
            }

        # Set new mode
        orchestrator.execution_mode = new_mode

        return {
            "status": "success",
            "old_mode": old_mode.value,
            "new_mode": new_mode.value,
        }

    except RuntimeError:
        return {"status": "error", "error": "Execution mode tools not initialized"}
    except ValueError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        logger.error(f"Error setting execution mode: {e}")
        return {"status": "error", "error": str(e)}


def confirm_and_set_auto_mode() -> Dict[str, Any]:
    """
    Confirm and set AUTO execution mode.

    Used after user confirms they want AUTO mode.
    This function bypasses the confirmation check.

    Returns:
        Dict with status and mode information
    """
    try:
        from src.autogen_agents import ExecutionMode

        orchestrator = _get_orchestrator()
        old_mode = orchestrator.execution_mode
        orchestrator.execution_mode = ExecutionMode.AUTO

        return {
            "status": "success",
            "old_mode": old_mode.value,
            "new_mode": "auto",
        }

    except RuntimeError:
        return {"status": "error", "error": "Execution mode tools not initialized"}
    except Exception as e:
        logger.error(f"Error setting auto mode: {e}")
        return {"status": "error", "error": str(e)}


def get_execution_mode() -> Dict[str, Any]:
    """
    Get the current execution mode as structured data.

    Returns:
        Dict with current mode and descriptions

    Example:
        >>> get_execution_mode()
        {'status': 'success', 'current_mode': 'confirm', 'description': '...'}
    """
    try:
        orchestrator = _get_orchestrator()
        current_mode = orchestrator.execution_mode

        descriptions = {
            "confirm": "Requires human approval for each trade",
            "auto": "Executes trades automatically (within risk limits)",
            "paper": "Paper trading only, no real money",
            "disabled": "Trading completely disabled",
        }

        return {
            "status": "success",
            "current_mode": current_mode.value,
            "description": descriptions.get(current_mode.value, "Unknown mode"),
            "all_modes": list(descriptions.keys()),
        }

    except RuntimeError:
        return {"status": "error", "error": "Execution mode tools not initialized"}
    except Exception as e:
        logger.error(f"Error getting execution mode: {e}")
        return {"status": "error", "error": str(e)}


def format_mode_change_result(result: Dict[str, Any]) -> str:
    """
    Format a mode change result as display string.

    Args:
        result: Result dict from set_execution_mode()

    Returns:
        Formatted display string
    """
    if result["status"] == "error":
        lines = [f"❌ {result.get('error', 'Unknown error')}"]
        if "valid_modes" in result:
            lines.append("ℹ️  Valid modes: " + ", ".join(result["valid_modes"]))
        return "\n".join(lines)

    if result["status"] == "requires_confirmation":
        return (
            "\n⚠️  WARNING: Switching to AUTO mode\n"
            "   This will execute trades automatically without confirmation.\n"
            "   Risk limits and position sizing will still apply."
        )

    # Success
    old_mode = result.get("old_mode", "unknown").upper()
    new_mode = result.get("new_mode", "unknown").upper()
    lines = [f"\n✅ Execution mode changed: {old_mode} → {new_mode}"]

    # Mode-specific guidance
    if new_mode == "CONFIRM":
        lines.append("   • Trades will require your approval before execution")
    elif new_mode == "AUTO":
        lines.append("   • Trades will execute automatically (within risk limits)")
        lines.append("   • Use 'cancel all orders' to stop pending trades")
    elif new_mode == "PAPER":
        lines.append("   • All trades will be simulated (no real money)")
    elif new_mode == "DISABLED":
        lines.append("   • Trading is now disabled")
        lines.append("   • No trades will be executed")

    return "\n".join(lines)


# ============================================================================
# FunctionTool Instances
# ============================================================================


show_execution_mode_tool = FunctionTool(
    func=show_execution_mode,
    name="show_execution_mode",
    description="Show the current execution mode with descriptions of all modes",
)

get_execution_mode_tool = FunctionTool(
    func=get_execution_mode,
    name="get_execution_mode",
    description="Get current execution mode as structured data for programmatic use",
)

set_execution_mode_tool = FunctionTool(
    func=set_execution_mode,
    name="set_execution_mode",
    description="Set execution mode (confirm, auto, paper, disabled)",
)


# Export list for CLI tools registry (registered via __init__.py auto-discovery)
CLI_EXECUTION_MODE_TOOLS = [
    show_execution_mode_tool,
    get_execution_mode_tool,
    set_execution_mode_tool,
]

__all__ = [
    # Setup
    "set_orchestrator",
    # Display functions
    "show_execution_mode",
    "format_mode_change_result",
    # Data functions
    "get_execution_mode",
    "set_execution_mode",
    "confirm_and_set_auto_mode",
    # FunctionTools
    "CLI_EXECUTION_MODE_TOOLS",
    "show_execution_mode_tool",
    "get_execution_mode_tool",
    "set_execution_mode_tool",
    # Category
    "EXECUTION_MODE_TOOLS",
]
