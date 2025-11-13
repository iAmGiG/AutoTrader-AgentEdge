"""
Order execution implementations.

Available:
- AlpacaExecutionManager: Executes via Alpaca broker (integrates OrderManager)
"""

from .alpaca_execution_manager import AlpacaExecutionManager

__all__ = [
    "AlpacaExecutionManager",
]
