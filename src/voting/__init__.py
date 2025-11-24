"""
Multi-Indicator Voting System for RH2MAS

Core voting architecture implementing ensemble decision-making for trading strategies.
Transforms single MACD approach to multi-indicator voting system targeting 90% accuracy.

Key Components:
- BaseVotingStrategy: Abstract foundation for all voting strategies
- BasicVotingStrategy: Equal-weighted voting implementation (Issue #250)

Future Components (Issues #277-289):
- RSI integration (#277)
- Bollinger Bands (#278)
- Volume confirmation (#279)
- Weighted voting (#281)
- Market regime adaptation (#284)
- Production readiness (#287-289)
"""

from .base_voting_strategy import (
    BaseVotingStrategy,
    IndicatorSignal,
    MarketRegime,
    SignalStrength,
    VotingDecision,
)
from .basic_voting_strategy import BasicVotingStrategy

__all__ = [
    "BaseVotingStrategy",
    "BasicVotingStrategy",
    "IndicatorSignal",
    "VotingDecision",
    "SignalStrength",
    "MarketRegime",
]

# Version info for Issue tracking
__version__ = "0.1.0"  # Issue #250 - Core Voting Architecture
__issue_status__ = {
    "250": "COMPLETE",  # Core Voting Architecture
    "277": "PENDING",  # RSI Implementation
    "278": "PENDING",  # Bollinger Bands
    "279": "PENDING",  # Volume Confirmation
    "280": "PENDING",  # Ensemble Metrics Dashboard
    "281": "PENDING",  # Weighted Voting System
}
