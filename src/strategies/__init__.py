"""
Trading strategy implementations.

Available strategies:
- VoterStrategy: MACD+RSI voting stub (MVP testing)
- RealVoterStrategy: Production MACD+RSI voting (0.856 Sharpe)
- OptionsStrategy: Options analysis (future #330)
- MultiAgentStrategy: Multi-agent coordination (future #331)
"""

from .real_voter_strategy import RealVoterStrategy
from .voter_strategy import VoterStrategy

__all__ = [
    "VoterStrategy",
    "RealVoterStrategy",
]
