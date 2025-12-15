"""
Specialized trading agents.

Production Ready:
- VoterAgent: MACD+RSI voting (0.856 Sharpe ratio validated)
- MultiTimeframeVoter: Multi-timeframe ranked voting (#395)

In Development:
- ScannerAgent: Market scanning and ticker discovery
- RiskAgent: Risk assessment and position sizing
- ExecutorAgent: Trade execution and order management
"""

from .executor_agent import ExecutorAgent, create_executor_agent
from .multi_timeframe_voter import (
    MultiTimeframeResult,
    MultiTimeframeVoter,
    TimeframeResult,
    evaluate_multi_timeframe,
    get_multi_timeframe_voter,
)
from .risk_agent import RiskAgent, create_risk_agent
from .scanner_agent import ScanConfig, ScannerAgent, ScanResult, create_scanner_agent
from .voter_agent import VoterAgent, create_voter_agent

__all__ = [
    # Production Ready
    "VoterAgent",
    "create_voter_agent",
    "MultiTimeframeVoter",
    "MultiTimeframeResult",
    "TimeframeResult",
    "evaluate_multi_timeframe",
    "get_multi_timeframe_voter",
    # In Development
    "ExecutorAgent",
    "create_executor_agent",
    "RiskAgent",
    "create_risk_agent",
    "ScannerAgent",
    "create_scanner_agent",
    "ScanConfig",
    "ScanResult",
]
