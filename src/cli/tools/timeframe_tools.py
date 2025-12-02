"""
Timeframe CLI Tools - FunctionTool wrappers for timeframe management.

Issue #456: Extract timeframe tools from cli_session.py.
Issue #365: Natural language timeframe commands (already implemented).

This module wraps the existing TimeframeCommands class methods as FunctionTool
instances for integration with the AutoGen agent architecture.

Original Implementation: src/cli/timeframe_commands.py
Pattern: Pure function wrappers → FunctionTool → Registry
"""

from typing import Dict, Optional

from autogen_core.tools import FunctionTool

from . import TIMEFRAME_TOOLS, register_cli_tool
from src.cli.timeframe_commands import get_timeframe_commands

# Get singleton instance for all tool functions
_tf_commands = get_timeframe_commands()


# ============================================================================
# Pure Function Wrappers
# ============================================================================
# These functions wrap the TimeframeCommands methods to provide a functional
# interface that works well with FunctionTool


def list_timeframes(verbose: bool = False) -> str:
    """
    List all available timeframes.

    Shows all supported trading timeframes with optional descriptions.
    Indicates the currently active timeframe.

    Args:
        verbose: Show detailed descriptions for each timeframe

    Returns:
        Formatted string listing all timeframes

    Example:
        >>> list_timeframes()
        '📊 Available Timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo'
        >>> list_timeframes(verbose=True)
        '📊 Available Timeframes:\\n  [✓] 1d - Daily bars (recommended)\\n  [ ] 1h - Hourly bars...'
    """
    return _tf_commands.list_timeframes(verbose=verbose)


def set_timeframe(timeframe: str) -> str:
    """
    Change the active trading timeframe.

    Updates the global timeframe used for all trading operations.
    Validates the timeframe before applying.

    Args:
        timeframe: New timeframe to set (e.g., '1d', '1h', '5m')

    Returns:
        Success or error message

    Example:
        >>> set_timeframe('1h')
        '✅ Timeframe changed from 1d to 1h'
        >>> set_timeframe('invalid')
        '❌ Invalid timeframe: invalid'
    """
    return _tf_commands.set_timeframe(timeframe)


def show_current_timeframe() -> str:
    """
    Show the currently active timeframe.

    Returns:
        Formatted string showing current timeframe with description

    Example:
        >>> show_current_timeframe()
        '📍 Current Timeframe: 1d (Daily bars - recommended for swing trading)'
    """
    return _tf_commands.show_current_timeframe()


def show_timeframe_recommendations() -> str:
    """
    Show timeframe recommendations for different trading styles.

    Provides guidance on which timeframes are best suited for different
    trading strategies (scalping, day trading, swing trading, etc.).

    Returns:
        Formatted string with recommendations by trading style

    Example:
        >>> show_timeframe_recommendations()
        '📈 Timeframe Recommendations\\n🎯 Scalping: 1m, 5m\\n📊 Day Trading: 15m, 30m, 1h...'
    """
    return _tf_commands.show_timeframe_recommendations()


def validate_and_info(timeframe: str) -> str:
    """
    Validate a timeframe and show detailed information.

    Checks if a timeframe is valid and provides detailed information
    about it if valid.

    Args:
        timeframe: Timeframe to validate and describe

    Returns:
        Validation result and info, or error message

    Example:
        >>> validate_and_info('1d')
        'ℹ️  1d (current)\\nDaily bars - recommended for swing trading'
        >>> validate_and_info('invalid')
        '❌ Invalid timeframe: invalid'
    """
    return _tf_commands.validate_and_info(timeframe)


def get_timeframe_for_agent(command: str, arg: Optional[str] = None) -> Dict:
    """
    Get timeframe data for agents (structured data, no formatting).

    Provides timeframe information in a structured format suitable for
    programmatic consumption by agents.

    Args:
        command: Command to execute ('current', 'set', 'list', 'validate', 'info', 'recommendations')
        arg: Optional argument for the command

    Returns:
        Dictionary with structured timeframe data

    Example:
        >>> get_timeframe_for_agent('current')
        {'type': 'current_timeframe', 'timeframe': '1d'}
        >>> get_timeframe_for_agent('set', '1h')
        {'success': True, 'message': 'Timeframe changed...'}
    """
    return _tf_commands.get_for_agent(command, arg)


# ============================================================================
# FunctionTool Instances
# ============================================================================
# Each function is wrapped in a FunctionTool for AutoGen integration


list_timeframes_tool = FunctionTool(
    func=list_timeframes,
    name="list_timeframes",
    description="List all available trading timeframes with optional descriptions",
)

set_timeframe_tool = FunctionTool(
    func=set_timeframe,
    name="set_timeframe",
    description="Change the active trading timeframe (e.g., '1d', '1h', '5m')",
)

show_current_timeframe_tool = FunctionTool(
    func=show_current_timeframe,
    name="show_current_timeframe",
    description="Show the currently active trading timeframe",
)

show_timeframe_recommendations_tool = FunctionTool(
    func=show_timeframe_recommendations,
    name="show_timeframe_recommendations",
    description="Show timeframe recommendations for different trading styles",
)

validate_timeframe_tool = FunctionTool(
    func=validate_and_info,
    name="validate_timeframe",
    description="Validate a timeframe and show detailed information about it",
)

get_timeframe_for_agent_tool = FunctionTool(
    func=get_timeframe_for_agent,
    name="get_timeframe_for_agent",
    description="Get structured timeframe data for programmatic use by agents",
)


# ============================================================================
# Tool Registration
# ============================================================================
# Register all timeframe tools in the global registry


register_cli_tool(list_timeframes_tool, category=TIMEFRAME_TOOLS)
register_cli_tool(set_timeframe_tool, category=TIMEFRAME_TOOLS)
register_cli_tool(show_current_timeframe_tool, category=TIMEFRAME_TOOLS)
register_cli_tool(show_timeframe_recommendations_tool, category=TIMEFRAME_TOOLS)
register_cli_tool(validate_timeframe_tool, category=TIMEFRAME_TOOLS)
register_cli_tool(get_timeframe_for_agent_tool, category=TIMEFRAME_TOOLS)


# Export tools for direct import
CLI_TIMEFRAME_TOOLS = [
    list_timeframes_tool,
    set_timeframe_tool,
    show_current_timeframe_tool,
    show_timeframe_recommendations_tool,
    validate_timeframe_tool,
    get_timeframe_for_agent_tool,
]


__all__ = [
    # Functions
    "list_timeframes",
    "set_timeframe",
    "show_current_timeframe",
    "show_timeframe_recommendations",
    "validate_and_info",
    "get_timeframe_for_agent",
    # Tools
    "list_timeframes_tool",
    "set_timeframe_tool",
    "show_current_timeframe_tool",
    "show_timeframe_recommendations_tool",
    "validate_timeframe_tool",
    "get_timeframe_for_agent_tool",
    # Collections
    "CLI_TIMEFRAME_TOOLS",
]
