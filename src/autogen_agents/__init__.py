"""
AutoGen Agents Package - Multi-agent trading system components

This package provides:
- Agent Factory: Centralized agent creation with typed enums
- Agent Bus: Pub-Sub messaging for inter-agent communication
- Trading Agents: VoterAgent (production-ready), Scanner, Risk, Executor
"""

from .agent_bus import (
                        AgentBus,
                        AgentMessage,
                        EventType,
                        Subscription,
                        create_message,
                        get_agent_bus,
                        publish_result,
                        publish_signal,
                        publish_trade_executed,
)

# Agent Infrastructure (Issue #390)
from .agent_factory import (
                        AgentConfig,
                        AgentFactory,
                        AgentInstance,
                        AgentType,
                        create_agent,
                        create_executor,
                        create_orchestrator,
                        create_risk,
                        create_scanner,
                        create_voter,
                        get_agent_factory,
)

# Production-ready agents
from .voter_agent import VoterAgent, create_voter_agent

# TODO: Complete these agents before importing
# from .scanner_agent import ScannerAgent, create_scanner_agent
# from .risk_agent import RiskAgent, create_risk_agent
# from .executor_agent import ExecutorAgent, create_executor_agent
# from .orchestrator import TradingOrchestrator, create_trading_orchestrator

__all__ = [
    # Agent Infrastructure
    "AgentType",
    "AgentConfig",
    "AgentInstance",
    "AgentFactory",
    "get_agent_factory",
    "create_agent",
    "create_voter",
    "create_scanner",
    "create_risk",
    "create_executor",
    "create_orchestrator",
    # Agent Bus
    "EventType",
    "AgentMessage",
    "Subscription",
    "AgentBus",
    "get_agent_bus",
    "create_message",
    "publish_result",
    "publish_signal",
    "publish_trade_executed",
    # Production Agents
    "VoterAgent",
    "create_voter_agent",
    # TODO: Add others when completed
    # 'ScannerAgent', 'create_scanner_agent',
    # 'RiskAgent', 'create_risk_agent',
    # 'ExecutorAgent', 'create_executor_agent',
    # 'TradingOrchestrator', 'create_trading_orchestrator'
]
