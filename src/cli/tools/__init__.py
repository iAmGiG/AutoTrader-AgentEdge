"""
CLI Tools - FunctionTool-based command handlers.

Issue #433: Refactor cli_session.py to use FunctionTool architecture.

This module contains all CLI command implementations as FunctionTool objects,
following the same pattern as src/data_sources/tools.py and base_agent.py.

Architecture Benefits:
- Type hints auto-generate schemas
- Pure functions → easy to test
- Consistent with agent-based design
- Tools can be reused by agents
- ~3000 line monolith → modular 200-line files
"""

from autogen_core.tools import FunctionTool

# Import all tool modules (will be added as we extract them)
# from .mode_tools import CLI_MODE_TOOLS
# from .portfolio_tools import CLI_PORTFOLIO_TOOLS
# from .order_tools import CLI_ORDER_TOOLS
# from .scheduler_tools import CLI_SCHEDULER_TOOLS
# from .alert_tools import CLI_ALERT_TOOLS

# Registry of all CLI tools
CLI_TOOLS = []

# TODO: Populate as tools are extracted
# CLI_TOOLS = (
#     CLI_MODE_TOOLS +
#     CLI_PORTFOLIO_TOOLS +
#     CLI_ORDER_TOOLS +
#     CLI_SCHEDULER_TOOLS +
#     CLI_ALERT_TOOLS
# )

__all__ = [
    "CLI_TOOLS",
    "FunctionTool",
]
