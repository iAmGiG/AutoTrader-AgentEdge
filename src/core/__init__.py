"""
Core trading system architecture.

This package contains the foundational interfaces, models, and orchestrator
for the new plugin-based architecture.

Legacy components (autogen_agents, old strategies) are imported separately.
"""

# Event Bus Infrastructure (Issue #397)
from .event_bus import Event, EventBus, EventPriority, get_event_bus
from .events import (
    EventType,
    # Market events
    MarketDataPayload,
    MarketOpportunityPayload,
    create_market_data_event,
    create_market_opportunity_event,
    # Signal events
    SignalPayload,
    create_signal_event,
    # Risk events
    RiskAssessmentPayload,
    RiskAlertPayload,
    create_risk_assessment_event,
    create_risk_alert_event,
    # Order events
    OrderPayload,
    create_order_event,
    # Position events
    PositionPayload,
    StopAdjustmentPayload,
    create_position_event,
    create_stop_adjustment_event,
    # System events
    SystemErrorPayload,
    AgentHeartbeatPayload,
    create_system_error_event,
    create_agent_heartbeat_event,
)
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
    # Event Bus Infrastructure (Issue #397)
    "Event",
    "EventBus",
    "EventPriority",
    "EventType",
    "get_event_bus",
    # Event payloads
    "MarketDataPayload",
    "MarketOpportunityPayload",
    "SignalPayload",
    "RiskAssessmentPayload",
    "RiskAlertPayload",
    "OrderPayload",
    "PositionPayload",
    "StopAdjustmentPayload",
    "SystemErrorPayload",
    "AgentHeartbeatPayload",
    # Event factory functions
    "create_market_data_event",
    "create_market_opportunity_event",
    "create_signal_event",
    "create_risk_assessment_event",
    "create_risk_alert_event",
    "create_order_event",
    "create_position_event",
    "create_stop_adjustment_event",
    "create_system_error_event",
    "create_agent_heartbeat_event",
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
