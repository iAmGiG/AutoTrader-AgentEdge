"""
CLI Utilities - Support modules for the CLI session.

This module contains utility classes and functions used by cli_session.py
and other CLI components.

Modules:
- ticker_completer: Tab completion for ticker symbols (readline integration)
- trading_tips: Load and display trading tips from YAML config
- help_system: Help command handling and documentation
- decision_formatter: Format trading decisions for human review
- suggestion_display: Display formatting for trade suggestions (Issue #436)
"""

from src.cli.utils.help_system import HelpSystem
from src.cli.utils.suggestion_display import (
                                              calc_pct,
                                              display_position_context,
                                              display_result,
                                              display_suggestion,
                                              get_trade_direction,
)
from src.cli.utils.ticker_completer import (
                                              READLINE_AVAILABLE,
                                              TickerCompleter,
                                              get_ticker_completer,
                                              is_powershell,
                                              readline,
)
from src.cli.utils.trading_tips import (
                                              display_trading_tips,
                                              get_tips_dict,
                                              load_trading_tips,
                                              show_trading_tips,
)

__all__ = [
    # Ticker completer
    "READLINE_AVAILABLE",
    "readline",
    "TickerCompleter",
    "get_ticker_completer",
    "is_powershell",
    # Trading tips
    "load_trading_tips",
    "get_tips_dict",
    "show_trading_tips",
    "display_trading_tips",
    # Help system
    "HelpSystem",
    # Suggestion display
    "calc_pct",
    "get_trade_direction",
    "display_position_context",
    "display_suggestion",
    "display_result",
]
