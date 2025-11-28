"""
Core trading system architecture.

This package contains the foundational interfaces, models, and orchestrator
for the new plugin-based architecture.

For agent communication, use src/autogen_agents/agent_bus.py (Issue #390).
Legacy components (autogen_agents, old strategies) are imported separately.
"""

from .interfaces import ExecutionManager, InputParser, RiskManager, StrategyAnalyzer

# New plugin architecture
from .models import (
                         AnalysisResult,
                         AssetType,
                         OrderResult,
                         OrderType,
                         RiskAssessment,
                         SessionState,
                         Signal,
                         TimeInForce,
                         TradeDecision,
                         TradeRequest,
                         TradeSuggestion,
)
from .trading_orchestrator import TradingOrchestrator

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
