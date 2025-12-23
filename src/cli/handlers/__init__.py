"""
CLI Handlers - Extracted from cli_session.py for modular organization.

Issue #509: Refactor cli_session.py into modular handlers
"""

from src.cli.handlers.trade_handler import TradeHandler

__all__ = ["TradeHandler"]
