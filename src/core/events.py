"""
Event Type Definitions - Trading System Events

Defines all event types used by agents in the AgentEdge trading system.
Each event type has a factory function for type-safe event creation.

Issue #397: Event Bus Infrastructure
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .event_bus import Event, EventPriority


class EventType(str, Enum):
    """
    Enumeration of all event types in the trading system.

    Naming convention: {DOMAIN}_{ACTION}
    """

    # Market Data Events (from ScannerAgent)
    MARKET_DATA_UPDATE = "market.data.update"
    MARKET_OPPORTUNITY = "market.opportunity"
    MARKET_SCAN_COMPLETE = "market.scan.complete"

    # Signal Events (from VoterAgent)
    SIGNAL_GENERATED = "signal.generated"
    SIGNAL_UPDATED = "signal.updated"
    SIGNAL_EXPIRED = "signal.expired"

    # Risk Events (from RiskAgent)
    RISK_ASSESSMENT = "risk.assessment"
    RISK_ALERT = "risk.alert"
    RISK_LIMIT_BREACH = "risk.limit.breach"

    # Execution Events (from ExecutorAgent)
    ORDER_SUBMITTED = "order.submitted"
    ORDER_FILLED = "order.filled"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"
    ORDER_PARTIAL_FILL = "order.partial_fill"

    # Position Events (from PositionManager)
    POSITION_OPENED = "position.opened"
    POSITION_CLOSED = "position.closed"
    POSITION_UPDATED = "position.updated"
    STOP_ADJUSTED = "position.stop.adjusted"

    # Portfolio Events (from PortfolioManager)
    PORTFOLIO_REBALANCE = "portfolio.rebalance"
    PORTFOLIO_ALLOCATION = "portfolio.allocation"
    PORTFOLIO_SUMMARY = "portfolio.summary"

    # System Events
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    SYSTEM_ERROR = "system.error"
    AGENT_REGISTERED = "system.agent.registered"
    AGENT_HEARTBEAT = "system.agent.heartbeat"


# ============================================================
# Market Data Events
# ============================================================


@dataclass
class MarketDataPayload:
    """Payload for market data events."""

    symbol: str
    price: float
    volume: Optional[int] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    timestamp: Optional[datetime] = None


@dataclass
class MarketOpportunityPayload:
    """Payload for market opportunity events."""

    symbol: str
    signal: str  # BUY, SELL, HOLD
    confidence: float
    price: float
    indicators: Dict[str, Any]
    timeframe: str = "1d"


def create_market_data_event(
    source: str,
    symbol: str,
    price: float,
    volume: Optional[int] = None,
    **kwargs,
) -> Event:
    """Create a market data update event."""
    return Event(
        event_type=EventType.MARKET_DATA_UPDATE.value,
        source=source,
        data=MarketDataPayload(
            symbol=symbol,
            price=price,
            volume=volume,
            **kwargs,
        ),
    )


def create_market_opportunity_event(
    source: str,
    symbol: str,
    signal: str,
    confidence: float,
    price: float,
    indicators: Dict[str, Any],
    timeframe: str = "1d",
) -> Event:
    """Create a market opportunity event."""
    return Event(
        event_type=EventType.MARKET_OPPORTUNITY.value,
        source=source,
        data=MarketOpportunityPayload(
            symbol=symbol,
            signal=signal,
            confidence=confidence,
            price=price,
            indicators=indicators,
            timeframe=timeframe,
        ),
        priority=EventPriority.HIGH,
    )


# ============================================================
# Signal Events
# ============================================================


@dataclass
class SignalPayload:
    """Payload for trading signal events."""

    symbol: str
    action: str  # BUY, SELL, HOLD
    strength: str  # STRONG, MODERATE, WEAK
    confidence: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timeframe: str = "1d"
    indicators: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None


def create_signal_event(
    source: str,
    symbol: str,
    action: str,
    strength: str,
    confidence: float,
    price: float,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    timeframe: str = "1d",
    indicators: Optional[Dict[str, Any]] = None,
    reasoning: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Event:
    """Create a trading signal event."""
    return Event(
        event_type=EventType.SIGNAL_GENERATED.value,
        source=source,
        data=SignalPayload(
            symbol=symbol,
            action=action,
            strength=strength,
            confidence=confidence,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timeframe=timeframe,
            indicators=indicators,
            reasoning=reasoning,
        ),
        priority=EventPriority.HIGH,
        correlation_id=correlation_id,
    )


# ============================================================
# Risk Events
# ============================================================


@dataclass
class RiskAssessmentPayload:
    """Payload for risk assessment events."""

    symbol: str
    risk_score: float  # 0.0 (low risk) to 1.0 (high risk)
    max_position_size: int
    recommended_stop_loss: float
    factors: Dict[str, Any]
    approved: bool
    reason: Optional[str] = None


@dataclass
class RiskAlertPayload:
    """Payload for risk alert events."""

    alert_type: str  # POSITION_SIZE, DRAWDOWN, CONCENTRATION, etc.
    severity: str  # INFO, WARNING, CRITICAL
    message: str
    affected_symbols: List[str]
    metrics: Dict[str, Any]


def create_risk_assessment_event(
    source: str,
    symbol: str,
    risk_score: float,
    max_position_size: int,
    recommended_stop_loss: float,
    factors: Dict[str, Any],
    approved: bool,
    reason: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Event:
    """Create a risk assessment event."""
    return Event(
        event_type=EventType.RISK_ASSESSMENT.value,
        source=source,
        data=RiskAssessmentPayload(
            symbol=symbol,
            risk_score=risk_score,
            max_position_size=max_position_size,
            recommended_stop_loss=recommended_stop_loss,
            factors=factors,
            approved=approved,
            reason=reason,
        ),
        correlation_id=correlation_id,
    )


def create_risk_alert_event(
    source: str,
    alert_type: str,
    severity: str,
    message: str,
    affected_symbols: List[str],
    metrics: Dict[str, Any],
) -> Event:
    """Create a risk alert event."""
    priority = EventPriority.CRITICAL if severity == "CRITICAL" else EventPriority.HIGH
    return Event(
        event_type=EventType.RISK_ALERT.value,
        source=source,
        data=RiskAlertPayload(
            alert_type=alert_type,
            severity=severity,
            message=message,
            affected_symbols=affected_symbols,
            metrics=metrics,
        ),
        priority=priority,
    )


# ============================================================
# Execution Events
# ============================================================


@dataclass
class OrderPayload:
    """Payload for order events."""

    order_id: str
    symbol: str
    side: str  # BUY, SELL
    quantity: int
    order_type: str  # MARKET, LIMIT, STOP, BRACKET
    status: str  # SUBMITTED, FILLED, CANCELLED, REJECTED
    price: Optional[float] = None
    filled_price: Optional[float] = None
    filled_quantity: Optional[int] = None
    stop_price: Optional[float] = None
    limit_price: Optional[float] = None
    message: Optional[str] = None


def create_order_event(
    source: str,
    event_type: EventType,
    order_id: str,
    symbol: str,
    side: str,
    quantity: int,
    order_type: str,
    status: str,
    price: Optional[float] = None,
    filled_price: Optional[float] = None,
    filled_quantity: Optional[int] = None,
    correlation_id: Optional[str] = None,
    **kwargs,
) -> Event:
    """Create an order event."""
    return Event(
        event_type=event_type.value,
        source=source,
        data=OrderPayload(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            status=status,
            price=price,
            filled_price=filled_price,
            filled_quantity=filled_quantity,
            **kwargs,
        ),
        correlation_id=correlation_id,
    )


# ============================================================
# Position Events
# ============================================================


@dataclass
class PositionPayload:
    """Payload for position events."""

    symbol: str
    quantity: int
    entry_price: float
    current_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None


@dataclass
class StopAdjustmentPayload:
    """Payload for stop adjustment events."""

    symbol: str
    old_stop: float
    new_stop: float
    reason: str
    profit_percent: float


def create_position_event(
    source: str,
    event_type: EventType,
    symbol: str,
    quantity: int,
    entry_price: float,
    **kwargs,
) -> Event:
    """Create a position event."""
    return Event(
        event_type=event_type.value,
        source=source,
        data=PositionPayload(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            **kwargs,
        ),
    )


def create_stop_adjustment_event(
    source: str,
    symbol: str,
    old_stop: float,
    new_stop: float,
    reason: str,
    profit_percent: float,
) -> Event:
    """Create a stop adjustment event."""
    return Event(
        event_type=EventType.STOP_ADJUSTED.value,
        source=source,
        data=StopAdjustmentPayload(
            symbol=symbol,
            old_stop=old_stop,
            new_stop=new_stop,
            reason=reason,
            profit_percent=profit_percent,
        ),
    )


# ============================================================
# System Events
# ============================================================


@dataclass
class SystemErrorPayload:
    """Payload for system error events."""

    error_type: str
    message: str
    component: str
    severity: str  # WARNING, ERROR, CRITICAL
    stack_trace: Optional[str] = None


@dataclass
class AgentHeartbeatPayload:
    """Payload for agent heartbeat events."""

    agent_name: str
    agent_type: str
    status: str  # HEALTHY, DEGRADED, UNHEALTHY
    last_action: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


def create_system_error_event(
    source: str,
    error_type: str,
    message: str,
    component: str,
    severity: str = "ERROR",
    stack_trace: Optional[str] = None,
) -> Event:
    """Create a system error event."""
    priority = EventPriority.CRITICAL if severity == "CRITICAL" else EventPriority.HIGH
    return Event(
        event_type=EventType.SYSTEM_ERROR.value,
        source=source,
        data=SystemErrorPayload(
            error_type=error_type,
            message=message,
            component=component,
            severity=severity,
            stack_trace=stack_trace,
        ),
        priority=priority,
    )


def create_agent_heartbeat_event(
    agent_name: str,
    agent_type: str,
    status: str = "HEALTHY",
    last_action: Optional[str] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Event:
    """Create an agent heartbeat event."""
    return Event(
        event_type=EventType.AGENT_HEARTBEAT.value,
        source=agent_name,
        data=AgentHeartbeatPayload(
            agent_name=agent_name,
            agent_type=agent_type,
            status=status,
            last_action=last_action,
            metrics=metrics,
        ),
        priority=EventPriority.LOW,
    )
