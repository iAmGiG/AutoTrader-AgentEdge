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
from .executor_agent import ExecutorAgent, create_executor_agent
from .risk_agent import RiskAgent, create_risk_agent
from .scanner_agent import ScanConfig, ScannerAgent, ScanResult, create_scanner_agent

# TradingOrchestrator - Multi-agent workflow coordination (Issue #389)
from .trading_orchestrator import ExecutionMode, TradingOrchestrator, create_trading_orchestrator

# Production-ready agents
from .voter_agent import VoterAgent, create_voter_agent
from .workflow_state_manager import WorkflowPhase, WorkflowState

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
    "ExecutorAgent",
    "create_executor_agent",
    "RiskAgent",
    "create_risk_agent",
    # TradingOrchestrator
    "TradingOrchestrator",
    "create_trading_orchestrator",
    "ExecutionMode",
    "WorkflowPhase",
    "WorkflowState",
    # ScannerAgent
    "ScannerAgent",
    "create_scanner_agent",
    "ScanConfig",
    "ScanResult",
]
