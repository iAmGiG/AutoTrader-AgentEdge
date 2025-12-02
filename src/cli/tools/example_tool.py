"""
Example CLI Tool - Demonstrates FunctionTool pattern.

Issue #455: Create FunctionTool infrastructure.

This module shows how to create CLI command tools that follow the
FunctionTool pattern used throughout the AutoGen agent system.

Pattern:
1. Define pure functions with type hints
2. Wrap them in FunctionTool instances
3. Register tools in the global registry
4. Tools become available to CLI and agents

Benefits:
- Type hints auto-generate schemas
- Pure functions are easy to test
- Consistent with agent architecture
- Tools can be reused across CLI and agents
"""

from typing import Optional

from autogen_core.tools import FunctionTool

from . import TIMEFRAME_TOOLS, register_cli_tool


def echo_message(message: str, prefix: Optional[str] = None) -> str:
    """
    Echo a message with optional prefix.

    This is a simple example function showing the FunctionTool pattern.
    The function signature with type hints is used by AutoGen to generate
    the tool schema automatically.

    Args:
        message: The message to echo
        prefix: Optional prefix to prepend (default: "ECHO:")

    Returns:
        Formatted echo string

    Example:
        >>> echo_message("Hello World")
        'ECHO: Hello World'
        >>> echo_message("Test", prefix="DEBUG:")
        'DEBUG: Test'
    """
    if prefix is None:
        prefix = "ECHO:"
    return f"{prefix} {message}"


def greet_user(name: str, formal: bool = False) -> str:
    """
    Greet a user with optional formal style.

    Args:
        name: User's name
        formal: Use formal greeting style (default: False)

    Returns:
        Greeting message

    Example:
        >>> greet_user("Alice")
        'Hi Alice! 👋'
        >>> greet_user("Bob", formal=True)
        'Good day, Bob.'
    """
    if formal:
        return f"Good day, {name}."
    else:
        return f"Hi {name}! 👋"


# Create FunctionTool instances
# The type hints from the function signature are used to auto-generate schemas
echo_tool = FunctionTool(
    func=echo_message,
    name="echo_message",
    description="Echo a message with optional prefix (example tool)",
)

greet_tool = FunctionTool(
    func=greet_user,
    name="greet_user",
    description="Greet a user with optional formal style (example tool)",
)

# Register tools in the global registry
# Using a category helps organize tools
register_cli_tool(echo_tool, category=TIMEFRAME_TOOLS)  # Using timeframe as example
register_cli_tool(greet_tool, category=TIMEFRAME_TOOLS)

# Export tools for direct import if needed
EXAMPLE_TOOLS = [echo_tool, greet_tool]

__all__ = [
    "echo_message",
    "greet_user",
    "echo_tool",
    "greet_tool",
    "EXAMPLE_TOOLS",
]
