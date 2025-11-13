"""
Core trading system architecture.

This package contains the foundational interfaces, models, and orchestrator
for the new plugin-based architecture.

Legacy components (autogen_agents, old strategies) are imported separately.
"""

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