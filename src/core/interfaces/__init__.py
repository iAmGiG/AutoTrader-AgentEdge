"""
Core interfaces for the trading system.

These abstract base classes define the contracts that all implementations must follow.
This enables a plugin architecture where components can be swapped via configuration.
"""

from .execution_manager import ExecutionManager
from .input_parser import InputParser
from .risk_manager import RiskManager
from .strategy_analyzer import StrategyAnalyzer

__all__ = [
    "InputParser",
    "StrategyAnalyzer",
    "RiskManager",
    "ExecutionManager",
]
