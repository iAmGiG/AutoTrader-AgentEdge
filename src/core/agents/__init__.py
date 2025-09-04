# Core framework
from .base_agent import BaseAgent
from .tech_agent import TechAgent

# Current voting implementation  
from .simple_voting_orchestrator import SimpleVotingOrchestrator

# Legacy agents (may have dependencies on deprecated components)
try:
    from .strategy_agent import StrategyAgent
except ImportError:
    # StrategyAgent has dependencies on deprecated V0-V4 agents
    StrategyAgent = None

# V0-V4 sentiment agents deprecated (moved to src/deprecated/v0_v4_agents/)
# Now using minimal voting strategy: MACD + RSI
