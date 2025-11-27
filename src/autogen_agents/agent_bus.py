"""Agent Communication Bus for Multi-Agent Trading Coordination.

Pub-Sub message bus enabling decoupled inter-agent communication.
Ported from gex-llm-patterns and adapted for trading system events.

Issue #390: Agent Factory & Event Bus Infrastructure
Related: Issue #316 (Event Bus for agent communication)

Enables:
- Parallel agent execution
- Result sharing between agents
- Coordinated multi-asset analysis
- Async event-driven trading workflows
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Standard event types for trading agent communication."""

    # Market Data Events
    MARKET_DATA_FETCHED = "market_data_fetched"
    PRICE_UPDATE = "price_update"

    # Signal Events
    SIGNAL_DETECTED = "signal_detected"
    VOTING_COMPLETE = "voting_complete"

    # Risk Events
    RISK_VALIDATED = "risk_validated"
    RISK_REJECTED = "risk_rejected"
    POSITION_LIMIT_REACHED = "position_limit_reached"

    # Trade Events
    TRADE_PROPOSED = "trade_proposed"
    TRADE_APPROVED = "trade_approved"
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"

    # Position Events
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"
    STOP_TRIGGERED = "stop_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"

    # System Events
    ANALYSIS_COMPLETE = "analysis_complete"
    SCAN_COMPLETE = "scan_complete"
    ERROR = "error"
    CUSTOM = "custom"


@dataclass
class AgentMessage:
    """Message passed between agents via the bus.

    Attributes:
        source_agent: ID of the agent sending the message
        event_type: Type of event (from EventType enum or custom string)
        payload: Data payload of the message
        timestamp: When the message was created
        correlation_id: Optional ID to correlate related messages (e.g., trade lifecycle)
        priority: Message priority (higher = more urgent)
        ttl_seconds: Time-to-live before message expires
        symbol: Optional trading symbol this message relates to
    """

    source_agent: str
    event_type: Union[EventType, str]
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    priority: int = 0
    ttl_seconds: Optional[int] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if message has expired based on TTL."""
        if self.ttl_seconds is None:
            return False
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds

    def get_event_key(self) -> str:
        """Get standardized event key."""
        if isinstance(self.event_type, EventType):
            return self.event_type.value
        return str(self.event_type)


@dataclass
class Subscription:
    """Represents a subscription to events."""

    subscriber_id: str
    event_type: Union[EventType, str]
    callback: Callable[[AgentMessage], Any]
    filter_source: Optional[str] = None  # Only receive from specific source
    filter_symbol: Optional[str] = None  # Only receive for specific symbol


class AgentBus:
    """Pub-Sub message bus for inter-agent trading communication.

    Singleton pattern ensures all agents share the same bus instance.

    Features:
    - Subscribe to specific event types
    - Publish messages with automatic delivery
    - Wait for specific results with timeout
    - Gather multiple results in parallel
    - Message history for debugging and replay
    - Symbol-based filtering for multi-asset trading

    Example usage:
        bus = get_agent_bus()

        # Subscribe to signals
        bus.subscribe("risk_agent", EventType.SIGNAL_DETECTED, handle_signal)

        # Publish a signal
        await bus.publish(AgentMessage(
            source_agent="voter_agent",
            event_type=EventType.SIGNAL_DETECTED,
            symbol="AAPL",
            payload={"action": "BUY", "confidence": 0.85}
        ))
    """

    _instance: Optional["AgentBus"] = None

    def __new__(cls):
        """Singleton pattern for global bus access."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the message bus."""
        if self._initialized:
            return

        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._results: Dict[str, AgentMessage] = {}
        self._pending: Dict[str, asyncio.Event] = {}
        self._message_history: List[AgentMessage] = []
        self._max_history = 1000
        self._default_timeout = 30.0
        self._initialized = True

        logger.info("AgentBus initialized")

    def subscribe(
        self,
        subscriber_id: str,
        event_type: Union[EventType, str],
        callback: Callable[[AgentMessage], Any],
        filter_source: Optional[str] = None,
        filter_symbol: Optional[str] = None,
    ) -> str:
        """Subscribe to events of a specific type.

        Args:
            subscriber_id: ID of the subscribing agent
            event_type: Type of event to subscribe to
            callback: Function to call when event is received
            filter_source: Only receive from specific source agent
            filter_symbol: Only receive for specific trading symbol

        Returns:
            Subscription key for later unsubscription
        """
        event_key = event_type.value if isinstance(event_type, EventType) else event_type

        if event_key not in self._subscriptions:
            self._subscriptions[event_key] = []

        subscription = Subscription(
            subscriber_id=subscriber_id,
            event_type=event_type,
            callback=callback,
            filter_source=filter_source,
            filter_symbol=filter_symbol,
        )

        self._subscriptions[event_key].append(subscription)
        subscription_key = f"{subscriber_id}:{event_key}"

        logger.debug(f"Subscription added: {subscription_key}")
        return subscription_key

    def unsubscribe(self, subscriber_id: str, event_type: Union[EventType, str]) -> bool:
        """Unsubscribe from events.

        Args:
            subscriber_id: ID of the subscriber
            event_type: Event type to unsubscribe from

        Returns:
            True if subscription was found and removed
        """
        event_key = event_type.value if isinstance(event_type, EventType) else event_type

        if event_key not in self._subscriptions:
            return False

        original_count = len(self._subscriptions[event_key])
        self._subscriptions[event_key] = [
            sub for sub in self._subscriptions[event_key] if sub.subscriber_id != subscriber_id
        ]

        removed = len(self._subscriptions[event_key]) < original_count
        if removed:
            logger.debug(f"Unsubscribed {subscriber_id} from {event_key}")

        return removed

    async def publish(self, message: AgentMessage) -> int:
        """Publish a message to the bus.

        Args:
            message: The message to publish

        Returns:
            Number of subscribers notified
        """
        if message.is_expired():
            logger.warning(f"Message {message.message_id} already expired, not publishing")
            return 0

        event_key = message.get_event_key()
        result_key = f"{message.source_agent}:{event_key}"

        # Store result for direct retrieval
        self._results[result_key] = message

        # Add to history
        self._message_history.append(message)
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history :]

        # Notify subscribers
        notified = 0
        subscriptions = self._subscriptions.get(event_key, [])

        for subscription in subscriptions:
            # Apply source filter
            if subscription.filter_source and subscription.filter_source != message.source_agent:
                continue

            # Apply symbol filter
            if subscription.filter_symbol and subscription.filter_symbol != message.symbol:
                continue

            try:
                result = subscription.callback(message)
                # Handle async callbacks
                if asyncio.iscoroutine(result):
                    await result
                notified += 1
            except Exception as e:
                logger.error(f"Callback error for {subscription.subscriber_id}: {e}")

        # Signal waiters
        if result_key in self._pending:
            self._pending[result_key].set()

        logger.debug(f"Published {event_key} from {message.source_agent}, notified {notified}")
        return notified

    def publish_sync(self, message: AgentMessage) -> int:
        """Synchronous publish (creates event loop if needed).

        Args:
            message: The message to publish

        Returns:
            Number of subscribers notified
        """
        try:
            asyncio.get_running_loop()
            # We're in an async context, schedule for later
            asyncio.ensure_future(self.publish(message))
            return 0  # Can't wait synchronously in async context
        except RuntimeError:
            # No running loop, create one
            return asyncio.run(self.publish(message))

    async def wait_for_result(
        self,
        source_agent: str,
        event_type: Union[EventType, str],
        timeout: Optional[float] = None,
    ) -> Optional[AgentMessage]:
        """Wait for a specific agent's result.

        Args:
            source_agent: ID of the agent to wait for
            event_type: Type of event to wait for
            timeout: Seconds to wait (None uses default)

        Returns:
            The message if received, None on timeout
        """
        event_key = event_type.value if isinstance(event_type, EventType) else event_type
        result_key = f"{source_agent}:{event_key}"
        timeout = timeout or self._default_timeout

        # Check if already available
        if result_key in self._results:
            msg = self._results[result_key]
            if not msg.is_expired():
                return msg

        # Create event if not exists
        if result_key not in self._pending:
            self._pending[result_key] = asyncio.Event()
        else:
            # Reset for new wait
            self._pending[result_key].clear()

        try:
            await asyncio.wait_for(self._pending[result_key].wait(), timeout=timeout)
            return self._results.get(result_key)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for {result_key}")
            return None

    async def gather_results(
        self,
        queries: List[tuple],
        timeout: Optional[float] = None,
    ) -> Dict[str, Optional[AgentMessage]]:
        """Wait for multiple agent results in parallel.

        Args:
            queries: List of (source_agent, event_type) tuples
            timeout: Seconds to wait for all results

        Returns:
            Dictionary mapping result keys to messages
        """
        timeout = timeout or self._default_timeout * 2

        tasks = [self.wait_for_result(agent, event_type, timeout) for agent, event_type in queries]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            f"{q[0]}:{q[1].value if isinstance(q[1], EventType) else q[1]}": (
                r if not isinstance(r, Exception) else None
            )
            for q, r in zip(queries, results)
        }

    def get_result(
        self, source_agent: str, event_type: Union[EventType, str]
    ) -> Optional[AgentMessage]:
        """Get a stored result without waiting.

        Args:
            source_agent: ID of the source agent
            event_type: Type of event

        Returns:
            The stored message or None
        """
        event_key = event_type.value if isinstance(event_type, EventType) else event_type
        result_key = f"{source_agent}:{event_key}"
        msg = self._results.get(result_key)

        if msg and msg.is_expired():
            del self._results[result_key]
            return None

        return msg

    def get_history(
        self,
        event_type: Optional[Union[EventType, str]] = None,
        source_agent: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[AgentMessage]:
        """Get message history with optional filters.

        Args:
            event_type: Filter by event type
            source_agent: Filter by source agent
            symbol: Filter by trading symbol
            limit: Maximum messages to return

        Returns:
            List of matching messages (newest first)
        """
        messages = self._message_history.copy()
        messages.reverse()  # Newest first

        if event_type:
            event_key = event_type.value if isinstance(event_type, EventType) else event_type
            messages = [m for m in messages if m.get_event_key() == event_key]

        if source_agent:
            messages = [m for m in messages if m.source_agent == source_agent]

        if symbol:
            messages = [m for m in messages if m.symbol == symbol]

        return messages[:limit]

    def get_trade_history(
        self, symbol: Optional[str] = None, limit: int = 50
    ) -> List[AgentMessage]:
        """Get trade-related message history.

        Convenience method for debugging trade lifecycles.

        Args:
            symbol: Filter by trading symbol
            limit: Maximum messages to return

        Returns:
            List of trade-related messages
        """
        trade_events = {
            EventType.TRADE_PROPOSED.value,
            EventType.TRADE_APPROVED.value,
            EventType.TRADE_EXECUTED.value,
            EventType.TRADE_FAILED.value,
            EventType.POSITION_OPENED.value,
            EventType.POSITION_CLOSED.value,
        }

        messages = self._message_history.copy()
        messages.reverse()

        messages = [m for m in messages if m.get_event_key() in trade_events]

        if symbol:
            messages = [m for m in messages if m.symbol == symbol]

        return messages[:limit]

    def clear_results(self, older_than_seconds: Optional[int] = None) -> int:
        """Clear stored results.

        Args:
            older_than_seconds: Only clear results older than this

        Returns:
            Number of results cleared
        """
        if older_than_seconds is None:
            count = len(self._results)
            self._results.clear()
            return count

        cutoff = datetime.now()
        to_remove = []

        for key, msg in self._results.items():
            elapsed = (cutoff - msg.timestamp).total_seconds()
            if elapsed > older_than_seconds:
                to_remove.append(key)

        for key in to_remove:
            del self._results[key]

        return len(to_remove)

    def get_stats(self) -> Dict[str, Any]:
        """Get bus statistics.

        Returns:
            Dictionary with bus statistics
        """
        subscription_counts = {k: len(v) for k, v in self._subscriptions.items()}

        return {
            "total_subscriptions": sum(subscription_counts.values()),
            "subscriptions_by_event": subscription_counts,
            "stored_results": len(self._results),
            "history_size": len(self._message_history),
            "pending_waits": len(self._pending),
        }

    def reset(self) -> None:
        """Reset the bus (for testing)."""
        self._subscriptions.clear()
        self._results.clear()
        self._pending.clear()
        self._message_history.clear()
        logger.info("AgentBus reset")


# Module-level convenience functions
_bus: Optional[AgentBus] = None


def get_agent_bus() -> AgentBus:
    """Get the singleton AgentBus instance."""
    global _bus
    if _bus is None:
        _bus = AgentBus()
    return _bus


def create_message(
    source_agent: str,
    event_type: Union[EventType, str],
    payload: Dict[str, Any],
    symbol: Optional[str] = None,
    correlation_id: Optional[str] = None,
    priority: int = 0,
    ttl_seconds: Optional[int] = None,
) -> AgentMessage:
    """Convenience function to create a message.

    Args:
        source_agent: ID of the sending agent
        event_type: Type of event
        payload: Message data
        symbol: Trading symbol this message relates to
        correlation_id: Optional correlation ID
        priority: Message priority
        ttl_seconds: Optional time-to-live

    Returns:
        New AgentMessage instance
    """
    return AgentMessage(
        source_agent=source_agent,
        event_type=event_type,
        payload=payload,
        symbol=symbol,
        correlation_id=correlation_id,
        priority=priority,
        ttl_seconds=ttl_seconds,
    )


async def publish_result(
    source_agent: str,
    event_type: Union[EventType, str],
    payload: Dict[str, Any],
    **kwargs,
) -> int:
    """Convenience function to publish a result.

    Args:
        source_agent: ID of the sending agent
        event_type: Type of event
        payload: Message data
        **kwargs: Additional message parameters (symbol, correlation_id, etc.)

    Returns:
        Number of subscribers notified
    """
    message = create_message(source_agent, event_type, payload, **kwargs)
    return await get_agent_bus().publish(message)


# Trading-specific convenience functions
async def publish_signal(
    source_agent: str,
    symbol: str,
    action: str,
    confidence: float,
    **kwargs,
) -> int:
    """Publish a trading signal.

    Args:
        source_agent: ID of the agent detecting the signal
        symbol: Trading symbol
        action: Trading action (BUY, SELL, HOLD)
        confidence: Signal confidence (0.0 to 1.0)
        **kwargs: Additional payload data

    Returns:
        Number of subscribers notified
    """
    payload = {"action": action, "confidence": confidence, **kwargs}
    return await publish_result(source_agent, EventType.SIGNAL_DETECTED, payload, symbol=symbol)


async def publish_trade_executed(
    source_agent: str,
    symbol: str,
    order_id: str,
    shares: int,
    price: float,
    **kwargs,
) -> int:
    """Publish a trade execution event.

    Args:
        source_agent: ID of the executor agent
        symbol: Trading symbol
        order_id: Broker order ID
        shares: Number of shares traded
        price: Execution price
        **kwargs: Additional payload data

    Returns:
        Number of subscribers notified
    """
    payload = {"order_id": order_id, "shares": shares, "price": price, **kwargs}
    return await publish_result(source_agent, EventType.TRADE_EXECUTED, payload, symbol=symbol)
