"""
Core trading system architecture.

This package contains:
- Foundational interfaces, models, and orchestrator (new plugin architecture)
- Legacy agents, indicators, and strategies (existing components)
"""

# Legacy components (existing)
from .agents import *
from .indicators import *
from .strategies import *

# New plugin architecture
from .models import (
    Signal,
    AssetType,
    OrderType,
    TimeInForce,
    TradeRequest,
    AnalysisResult,
    RiskAssessment,
    TradeSuggestion,
    TradeDecision,
    OrderResult,
    SessionState,
)

from .trading_orchestrator import TradingOrchestrator

from .interfaces import (
    InputParser,
    StrategyAnalyzer,
    RiskManager,
    ExecutionManager,
)

__all__ = [
    # New architecture - Enums
    "Signal",
    "AssetType",
    "OrderType",
    "TimeInForce",

    # New architecture - Models
    "TradeRequest",
    "AnalysisResult",
    "RiskAssessment",
    "TradeSuggestion",
    "TradeDecision",
    "OrderResult",
    "SessionState",

    # New architecture - Orchestrator
    "TradingOrchestrator",

    # New architecture - Interfaces
    "InputParser",
    "StrategyAnalyzer",
    "RiskManager",
    "ExecutionManager",
]