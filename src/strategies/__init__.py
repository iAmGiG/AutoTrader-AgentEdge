"""
Trading strategy implementations.

Available strategies:
- VoterStrategy: MACD+RSI voting (production-validated, 0.856 Sharpe)
- OptionsStrategy: Options analysis (future #330)
- MultiAgentStrategy: Multi-agent coordination (future #331)
"""

from .voter_strategy import VoterStrategy

__all__ = [
    "VoterStrategy",
]
