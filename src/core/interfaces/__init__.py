"""
Core interfaces for the trading system.

These abstract base classes define the contracts that all implementations must follow.
This enables a plugin architecture where components can be swapped via configuration.
"""

from .input_parser import InputParser
from .strategy_analyzer import StrategyAnalyzer
from .risk_manager import RiskManager
from .execution_manager import ExecutionManager

__all__ = [
    "InputParser",
    "StrategyAnalyzer",
    "RiskManager",
    "ExecutionManager",
]
