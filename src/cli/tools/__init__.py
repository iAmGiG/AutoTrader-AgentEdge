"""
CLI Tools - FunctionTool-based command handlers.

Issue #433: Refactor cli_session.py to use FunctionTool architecture.
Issue #455: Create FunctionTool infrastructure with registry.
Issue #457: Portfolio and account display tools extraction (Phase 1C).

This module contains all CLI command implementations as FunctionTool objects,
following the same pattern as src/data_sources/tools.py and base_agent.py.

Architecture Benefits:
- Type hints auto-generate schemas
- Pure functions → easy to test
- Consistent with agent-based design
- Tools can be reused by agents
- ~3000 line monolith → modular 200-line files
"""

import logging
from typing import Dict, List, Optional

from autogen_core.tools import FunctionTool

logger = logging.getLogger(__name__)

# Tool category constants
MODE_TOOLS = "mode"
TIMEFRAME_TOOLS = "timeframe"
ACCOUNT_TOOLS = "account"
PORTFOLIO_TOOLS = "portfolio"
ORDER_TOOLS = "order"
SCHEDULER_TOOLS = "scheduler"
ALERT_TOOLS = "alert"


class CliToolRegistry:
    """
    Registry for CLI FunctionTools.

    Manages CLI command tools organized by category for easy discovery
    and integration with both CLI session and agents.

    Example:
        >>> registry = CliToolRegistry()
        >>> registry.register_tool(my_tool, category=MODE_TOOLS)
        >>> mode_tools = registry.get_tools_by_category(MODE_TOOLS)
        >>> all_tools = registry.get_all_tools()
    """

    def __init__(self):
        """Initialize empty tool registry."""
        self._tools: Dict[str, FunctionTool] = {}
        self._categories: Dict[str, List[str]] = {}

    def register_tool(self, tool: FunctionTool, category: Optional[str] = None) -> None:
        """
        Register a FunctionTool in the registry.

        Args:
            tool: FunctionTool instance to register
            category: Optional category for organization (e.g., "mode", "timeframe")
        """
        tool_name = tool.name

        if tool_name in self._tools:
            logger.warning(f"Tool '{tool_name}' already registered, overwriting")

        self._tools[tool_name] = tool

        if category:
            if category not in self._categories:
                self._categories[category] = []
            if tool_name not in self._categories[category]:
                self._categories[category].append(tool_name)

        logger.debug(f"Registered tool: {tool_name} (category: {category or 'none'})")

    def get_tool(self, tool_name: str) -> Optional[FunctionTool]:
        """
        Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            FunctionTool instance or None if not found
        """
        return self._tools.get(tool_name)

    def get_tools_by_category(self, category: str) -> List[FunctionTool]:
        """
        Get all tools in a category.

        Args:
            category: Category name (e.g., MODE_TOOLS)

        Returns:
            List of FunctionTool instances in the category
        """
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]

    def get_all_tools(self) -> List[FunctionTool]:
        """
        Get all registered tools.

        Returns:
            List of all FunctionTool instances
        """
        return list(self._tools.values())

    def get_categories(self) -> List[str]:
        """
        Get all category names.

        Returns:
            List of category names
        """
        return list(self._categories.keys())


# Global registry instance
_registry = CliToolRegistry()


def register_cli_tool(tool: FunctionTool, category: Optional[str] = None) -> None:
    """
    Register a CLI tool in the global registry.

    Args:
        tool: FunctionTool to register
        category: Optional category
    """
    _registry.register_tool(tool, category)


def get_cli_tool(tool_name: str) -> Optional[FunctionTool]:
    """
    Get a CLI tool by name.

    Args:
        tool_name: Name of the tool

    Returns:
        FunctionTool or None
    """
    return _registry.get_tool(tool_name)


def get_cli_tools_by_category(category: str) -> List[FunctionTool]:
    """
    Get all CLI tools in a category.

    Args:
        category: Category constant (e.g., MODE_TOOLS)

    Returns:
        List of FunctionTools
    """
    return _registry.get_tools_by_category(category)


def get_all_cli_tools() -> List[FunctionTool]:
    """
    Get all registered CLI tools.

    Returns:
        List of all CLI FunctionTools
    """
    return _registry.get_all_tools()


def _discover_and_register_tools() -> None:
    """
    Auto-discover and register tools from submodules.

    This function imports tool modules and automatically registers
    their tools in the global registry. Called at module import time.
    """
    # Phase 1A (#455): Example tools (for demonstration)
    try:
        from . import example_tool  # noqa: F401

        logger.debug("Loaded example_tool")
    except Exception as e:
        logger.warning(f"Failed to load example_tool: {e}")

    # Phase 1B (#456): Mode and timeframe tools
    try:
        from . import mode_tools  # noqa: F401

        logger.debug("Loaded mode_tools")
    except Exception as e:
        logger.warning(f"Failed to load mode_tools: {e}")

    try:
        from . import timeframe_tools  # noqa: F401

        logger.debug("Loaded timeframe_tools")
    except Exception as e:
        logger.warning(f"Failed to load timeframe_tools: {e}")

    # Phase 1C (#457): Portfolio and account display tools
    try:
        from .portfolio_tools import CLI_PORTFOLIO_TOOLS

        for tool in CLI_PORTFOLIO_TOOLS:
            register_cli_tool(tool, category=PORTFOLIO_TOOLS)
        logger.debug("Loaded portfolio_tools")
    except Exception as e:
        logger.warning(f"Failed to load portfolio_tools: {e}")

    try:
        from .account_display_tools import CLI_ACCOUNT_DISPLAY_TOOLS

        for tool in CLI_ACCOUNT_DISPLAY_TOOLS:
            register_cli_tool(tool, category=ACCOUNT_TOOLS)
        logger.debug("Loaded account_display_tools")
    except Exception as e:
        logger.warning(f"Failed to load account_display_tools: {e}")

    # Future phases: Additional tool categories
    # from .order_tools import CLI_ORDER_TOOLS  # #458
    # from .scheduler_tools import CLI_SCHEDULER_TOOLS  # #458
    # from .alert_tools import CLI_ALERT_TOOLS  # #458


# Auto-discover tools on import
_discover_and_register_tools()

# Export registry for direct access if needed
CLI_TOOL_REGISTRY = _registry

__all__ = [
    # Registry classes
    "CliToolRegistry",
    "CLI_TOOL_REGISTRY",
    # Helper functions
    "register_cli_tool",
    "get_cli_tool",
    "get_cli_tools_by_category",
    "get_all_cli_tools",
    # Category constants
    "MODE_TOOLS",
    "TIMEFRAME_TOOLS",
    "ACCOUNT_TOOLS",
    "PORTFOLIO_TOOLS",
    "ORDER_TOOLS",
    "SCHEDULER_TOOLS",
    "ALERT_TOOLS",
    # AutoGen core
    "FunctionTool",
]
