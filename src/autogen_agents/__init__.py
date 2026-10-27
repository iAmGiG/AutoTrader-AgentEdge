"""
Agents package - Multi-agent trading system components, on Microsoft Agent Framework
(#606; the package name is from its AutoGen days).

Organized Structure:
- core/: Base infrastructure (BaseAgent)
- agents/: Specialized trading agents (VoterAgent, ScannerAgent, RiskAgent, ExecutorAgent)
- orchestration/: Multi-agent coordination (TradingOrchestrator, AgentBus, AgentFactory)
- workflow/: Workflow state management and reporting

This package provides backward-compatible exports from the reorganized structure.
"""

# Specialized agents
from .agents import (
    ExecutorAgent,
    RiskAgent,
    ScanConfig,
    ScannerAgent,
    ScanResult,
    VoterAgent,
    create_executor_agent,
    create_risk_agent,
    create_scanner_agent,
    create_voter_agent,
)

# Core infrastructure
from .core import BaseAgent

# Orchestration components
from .orchestration import (
    AgentBus,
    AgentConfig,
    AgentFactory,
    AgentInstance,
    AgentMessage,
    AgentType,
    EventType,
    ExecutionMode,
    Subscription,
    TradingOrchestrator,
    create_agent,
    create_executor,
    create_message,
    create_orchestrator,
    create_risk,
    create_scanner,
    create_trading_orchestrator,
    create_voter,
    get_agent_bus,
    get_agent_factory,
    publish_result,
    publish_signal,
    publish_trade_executed,
)

# Workflow management
from .workflow import WorkflowPhase, WorkflowReporter, WorkflowState, WorkflowStateManager

__all__ = [
    # Core Infrastructure
    "BaseAgent",
    # Specialized Agents
    "VoterAgent",
    "create_voter_agent",
    "ExecutorAgent",
    "create_executor_agent",
    "RiskAgent",
    "create_risk_agent",
    "ScannerAgent",
    "create_scanner_agent",
    "ScanConfig",
    "ScanResult",
    # Orchestration
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
    "EventType",
    "AgentMessage",
    "Subscription",
    "AgentBus",
    "get_agent_bus",
    "create_message",
    "publish_result",
    "publish_signal",
    "publish_trade_executed",
    "TradingOrchestrator",
    "create_trading_orchestrator",
    "ExecutionMode",
    # Workflow
    "WorkflowPhase",
    "WorkflowState",
    "WorkflowStateManager",
    "WorkflowReporter",
]
