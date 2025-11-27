"""
Event Bus - Multi-Agent Communication Framework

Provides publish/subscribe pattern for agent coordination in the
AgentEdge trading system. Thread-safe and asyncio compatible.

Issue #397: Event Bus Infrastructure
"""

import asyncio
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Union
from uuid import uuid4

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels for processing order."""

    LOW = auto()
    NORMAL = auto()
    HIGH = auto()
    CRITICAL = auto()


@dataclass
class Event:
    """
    Base event class for all system events.

    Attributes:
        event_type: Type identifier for the event
        source: Name of the agent/component that published the event
        data: Event payload (type varies by event type)
        timestamp: When the event was created
        event_id: Unique identifier for this event
        priority: Processing priority
        correlation_id: Optional ID to link related events
    """

    event_type: str
    source: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    priority: EventPriority = EventPriority.NORMAL
    correlation_id: Optional[str] = None

    def __post_init__(self):
        """Ensure timestamp is set."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


# Type alias for event handlers
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], Any]  # Coroutine


class EventBus:
    """
    Thread-safe event bus with publish/subscribe pattern.

    Supports both synchronous and asynchronous event handlers.
    Maintains event history for debugging and replay.

    Example usage:
        bus = EventBus()

        # Subscribe to events
        bus.subscribe("signal", handle_signal)
        bus.subscribe("market_data", handle_market_data)

        # Publish events
        bus.publish(Event(
            event_type="signal",
            source="voter_agent",
            data={"symbol": "AAPL", "action": "BUY"}
        ))

        # Async publish
        await bus.publish_async(event)
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """Singleton pattern - ensure only one event bus exists."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, max_history: int = 1000):
        """
        Initialize the event bus.

        Args:
            max_history: Maximum number of events to keep in history
        """
        # Prevent re-initialization of singleton
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._async_handlers: Dict[str, List[AsyncEventHandler]] = defaultdict(list)
        self._event_history: List[Event] = []
        self._max_history = max_history
        self._lock = threading.RLock()
        self._paused: Set[str] = set()  # Paused event types
        self._initialized = True

        logger.info("EventBus initialized (singleton)")

    @classmethod
    def get_instance(cls) -> "EventBus":
        """Get the singleton EventBus instance."""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance._handlers.clear()
                cls._instance._async_handlers.clear()
                cls._instance._event_history.clear()
                cls._instance._paused.clear()
            cls._instance = None

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ) -> None:
        """
        Subscribe a synchronous handler to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Callback function to handle the event
            priority: Handler priority (higher priority handlers called first)
        """
        with self._lock:
            self._handlers[event_type].append(handler)
            logger.debug(f"Subscribed handler to '{event_type}'")

    def subscribe_async(
        self,
        event_type: str,
        handler: AsyncEventHandler,
    ) -> None:
        """
        Subscribe an async handler to an event type.

        Args:
            event_type: Type of event to subscribe to
            handler: Async callback function to handle the event
        """
        with self._lock:
            self._async_handlers[event_type].append(handler)
            logger.debug(f"Subscribed async handler to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> bool:
        """
        Unsubscribe a handler from an event type.

        Args:
            event_type: Type of event to unsubscribe from
            handler: Handler to remove

        Returns:
            True if handler was found and removed
        """
        with self._lock:
            if event_type in self._handlers:
                try:
                    self._handlers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed handler from '{event_type}'")
                    return True
                except ValueError:
                    pass

            if event_type in self._async_handlers:
                try:
                    self._async_handlers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed async handler from '{event_type}'")
                    return True
                except ValueError:
                    pass

        return False

    def publish(self, event: Event) -> int:
        """
        Publish an event to all subscribed handlers (synchronous).

        Args:
            event: The event to publish

        Returns:
            Number of handlers that processed the event
        """
        if event.event_type in self._paused:
            logger.debug(f"Event type '{event.event_type}' is paused, skipping")
            return 0

        # Add to history
        self._add_to_history(event)

        handlers_called = 0

        with self._lock:
            handlers = self._handlers.get(event.event_type, []).copy()

        for handler in handlers:
            try:
                handler(event)
                handlers_called += 1
            except Exception as e:
                logger.error(
                    f"Error in handler for '{event.event_type}': {e}",
                    exc_info=True,
                )

        logger.debug(
            f"Published '{event.event_type}' from '{event.source}' "
            f"to {handlers_called} handlers"
        )

        return handlers_called

    async def publish_async(self, event: Event) -> int:
        """
        Publish an event to all subscribed handlers (asynchronous).

        Calls both sync and async handlers.

        Args:
            event: The event to publish

        Returns:
            Number of handlers that processed the event
        """
        if event.event_type in self._paused:
            logger.debug(f"Event type '{event.event_type}' is paused, skipping")
            return 0

        # Add to history
        self._add_to_history(event)

        handlers_called = 0

        # Call sync handlers
        with self._lock:
            sync_handlers = self._handlers.get(event.event_type, []).copy()
            async_handlers = self._async_handlers.get(event.event_type, []).copy()

        # Execute sync handlers
        for handler in sync_handlers:
            try:
                handler(event)
                handlers_called += 1
            except Exception as e:
                logger.error(
                    f"Error in sync handler for '{event.event_type}': {e}",
                    exc_info=True,
                )

        # Execute async handlers concurrently
        if async_handlers:
            tasks = []
            for handler in async_handlers:
                try:
                    tasks.append(handler(event))
                except Exception as e:
                    logger.error(
                        f"Error creating task for '{event.event_type}': {e}",
                        exc_info=True,
                    )

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"Error in async handler for '{event.event_type}': {result}",
                            exc_info=True,
                        )
                    else:
                        handlers_called += 1

        logger.debug(
            f"Published async '{event.event_type}' from '{event.source}' "
            f"to {handlers_called} handlers"
        )

        return handlers_called

    def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining max size."""
        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)

    def get_event_history(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """
        Get event history with optional filtering.

        Args:
            event_type: Filter by event type
            source: Filter by source
            limit: Maximum number of events to return

        Returns:
            List of events matching the filter
        """
        with self._lock:
            events = self._event_history.copy()

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if source:
            events = [e for e in events if e.source == source]

        return events[-limit:]

    def clear_history(self) -> None:
        """Clear all event history."""
        with self._lock:
            self._event_history.clear()
        logger.info("Event history cleared")

    def clear_handlers(self, event_type: Optional[str] = None) -> None:
        """
        Clear handlers for an event type or all handlers.

        Args:
            event_type: Specific event type to clear, or None for all
        """
        with self._lock:
            if event_type:
                self._handlers[event_type].clear()
                self._async_handlers[event_type].clear()
                logger.info(f"Cleared handlers for '{event_type}'")
            else:
                self._handlers.clear()
                self._async_handlers.clear()
                logger.info("Cleared all handlers")

    def pause(self, event_type: str) -> None:
        """Pause processing of an event type."""
        with self._lock:
            self._paused.add(event_type)
        logger.info(f"Paused event type '{event_type}'")

    def resume(self, event_type: str) -> None:
        """Resume processing of a paused event type."""
        with self._lock:
            self._paused.discard(event_type)
        logger.info(f"Resumed event type '{event_type}'")

    def get_subscriber_count(self, event_type: str) -> int:
        """Get number of subscribers for an event type."""
        with self._lock:
            sync_count = len(self._handlers.get(event_type, []))
            async_count = len(self._async_handlers.get(event_type, []))
            return sync_count + async_count

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        with self._lock:
            event_types = set(self._handlers.keys()) | set(self._async_handlers.keys())
            return {
                "event_types": list(event_types),
                "total_handlers": sum(
                    len(h) for h in self._handlers.values()
                ) + sum(
                    len(h) for h in self._async_handlers.values()
                ),
                "history_size": len(self._event_history),
                "max_history": self._max_history,
                "paused_types": list(self._paused),
            }


# Convenience function to get the global event bus
def get_event_bus() -> EventBus:
    """Get the global EventBus singleton instance."""
    return EventBus.get_instance()
