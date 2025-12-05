"""
Multi-agent coordination and communication infrastructure.

Components:
- TradingOrchestrator: Main workflow coordinator (Issue #389)
- AgentFactory: Centralized agent creation (Issue #390)
- AgentBus: Pub-sub messaging for inter-agent communication
- Orchestrator: Legacy/simple orchestrator
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
from .trading_orchestrator import ExecutionMode, TradingOrchestrator, create_trading_orchestrator

__all__ = [
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
    # Agent Factory
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
    # Trading Orchestrator
    "TradingOrchestrator",
    "create_trading_orchestrator",
    "ExecutionMode",
]
