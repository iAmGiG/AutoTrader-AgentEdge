#!/usr/bin/env python3
"""
Unit tests for AgentBus.

Tests the pub-sub message bus for inter-agent communication.
Issue #390: Agent Factory & Event Bus Infrastructure
"""

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.autogen_agents.agent_bus import (
    AgentBus,
    AgentMessage,
    EventType,
    Subscription,
    create_message,
    get_agent_bus,
    publish_result,
)


class TestEventType(unittest.TestCase):
    """Test EventType enum."""

    def test_trading_events_exist(self):
        """Verify trading-specific events are defined."""
        expected_events = [
            "SIGNAL_DETECTED",
            "VOTING_COMPLETE",
            "RISK_VALIDATED",
            "TRADE_EXECUTED",
            "POSITION_OPENED",
            "POSITION_CLOSED",
        ]
        actual_events = [e.name for e in EventType]
        for expected in expected_events:
            self.assertIn(expected, actual_events)

    def test_event_values_are_lowercase(self):
        """Verify event values are lowercase strings."""
        for event_type in EventType:
            self.assertEqual(event_type.value, event_type.name.lower())


class TestAgentMessage(unittest.TestCase):
    """Test AgentMessage dataclass."""

    def test_message_creation(self):
        """Test basic message creation."""
        msg = AgentMessage(
            source_agent="voter_agent",
            event_type=EventType.SIGNAL_DETECTED,
            payload={"action": "BUY", "confidence": 0.85},
        )
        self.assertEqual(msg.source_agent, "voter_agent")
        self.assertEqual(msg.event_type, EventType.SIGNAL_DETECTED)
        self.assertEqual(msg.payload["action"], "BUY")
        self.assertIsNotNone(msg.message_id)
        self.assertIsNotNone(msg.timestamp)

    def test_message_with_symbol(self):
        """Test message with trading symbol."""
        msg = AgentMessage(
            source_agent="scanner",
            event_type=EventType.SIGNAL_DETECTED,
            payload={"pattern": "MACD crossover"},
            symbol="AAPL",
        )
        self.assertEqual(msg.symbol, "AAPL")

    def test_message_ttl(self):
        """Test message TTL expiration."""
        import time
        msg = AgentMessage(
            source_agent="test",
            event_type=EventType.CUSTOM,
            payload={},
            ttl_seconds=1,  # 1 second TTL
        )
        # Not expired yet
        self.assertFalse(msg.is_expired())
        # Wait for expiration
        time.sleep(1.1)
        self.assertTrue(msg.is_expired())

    def test_message_no_ttl(self):
        """Test message without TTL never expires."""
        msg = AgentMessage(
            source_agent="test",
            event_type=EventType.CUSTOM,
            payload={},
            ttl_seconds=None,
        )
        self.assertFalse(msg.is_expired())

    def test_get_event_key(self):
        """Test getting standardized event key."""
        msg1 = AgentMessage(
            source_agent="test",
            event_type=EventType.TRADE_EXECUTED,
            payload={},
        )
        self.assertEqual(msg1.get_event_key(), "trade_executed")

        msg2 = AgentMessage(
            source_agent="test",
            event_type="custom_event",
            payload={},
        )
        self.assertEqual(msg2.get_event_key(), "custom_event")

    def test_correlation_id(self):
        """Test correlation ID for related messages."""
        correlation_id = "trade-123"
        msg1 = AgentMessage(
            source_agent="voter",
            event_type=EventType.VOTING_COMPLETE,
            payload={},
            correlation_id=correlation_id,
        )
        msg2 = AgentMessage(
            source_agent="executor",
            event_type=EventType.TRADE_EXECUTED,
            payload={},
            correlation_id=correlation_id,
        )
        self.assertEqual(msg1.correlation_id, msg2.correlation_id)


class TestAgentBus(unittest.TestCase):
    """Test AgentBus singleton."""

    def setUp(self):
        """Reset bus before each test."""
        bus = get_agent_bus()
        bus.reset()

    def test_singleton_pattern(self):
        """Verify bus is a singleton."""
        bus1 = get_agent_bus()
        bus2 = get_agent_bus()
        self.assertIs(bus1, bus2)

    def test_subscribe(self):
        """Test subscribing to events."""
        bus = get_agent_bus()
        callback = lambda msg: None

        key = bus.subscribe("test_agent", EventType.SIGNAL_DETECTED, callback)

        self.assertIn("test_agent", key)
        self.assertIn("signal_detected", key)

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = get_agent_bus()
        callback = lambda msg: None

        bus.subscribe("test_agent", EventType.SIGNAL_DETECTED, callback)
        result = bus.unsubscribe("test_agent", EventType.SIGNAL_DETECTED)

        self.assertTrue(result)

    def test_unsubscribe_nonexistent(self):
        """Test unsubscribing when not subscribed."""
        bus = get_agent_bus()
        result = bus.unsubscribe("nonexistent", EventType.SIGNAL_DETECTED)
        self.assertFalse(result)

    def test_publish_and_callback(self):
        """Test publishing triggers callbacks."""
        bus = get_agent_bus()
        received = []

        def callback(msg):
            received.append(msg)

        bus.subscribe("listener", EventType.SIGNAL_DETECTED, callback)

        msg = create_message(
            source_agent="sender",
            event_type=EventType.SIGNAL_DETECTED,
            payload={"test": "data"},
        )

        notified = asyncio.run(bus.publish(msg))

        self.assertEqual(notified, 1)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].payload["test"], "data")

    def test_publish_no_subscribers(self):
        """Test publishing with no subscribers."""
        bus = get_agent_bus()

        msg = create_message(
            source_agent="sender",
            event_type=EventType.SIGNAL_DETECTED,
            payload={},
        )

        notified = asyncio.run(bus.publish(msg))
        self.assertEqual(notified, 0)

    def test_source_filter(self):
        """Test filtering by source agent."""
        bus = get_agent_bus()
        received = []

        def callback(msg):
            received.append(msg)

        # Only receive from "voter_agent"
        bus.subscribe(
            "listener",
            EventType.SIGNAL_DETECTED,
            callback,
            filter_source="voter_agent",
        )

        # Publish from wrong source
        msg1 = create_message(
            source_agent="scanner_agent",
            event_type=EventType.SIGNAL_DETECTED,
            payload={"from": "scanner"},
        )
        asyncio.run(bus.publish(msg1))

        # Publish from correct source
        msg2 = create_message(
            source_agent="voter_agent",
            event_type=EventType.SIGNAL_DETECTED,
            payload={"from": "voter"},
        )
        asyncio.run(bus.publish(msg2))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].source_agent, "voter_agent")

    def test_symbol_filter(self):
        """Test filtering by symbol."""
        bus = get_agent_bus()
        received = []

        def callback(msg):
            received.append(msg)

        # Only receive for AAPL
        bus.subscribe(
            "listener",
            EventType.SIGNAL_DETECTED,
            callback,
            filter_symbol="AAPL",
        )

        # Publish for wrong symbol
        msg1 = create_message(
            source_agent="voter",
            event_type=EventType.SIGNAL_DETECTED,
            payload={},
            symbol="MSFT",
        )
        asyncio.run(bus.publish(msg1))

        # Publish for correct symbol
        msg2 = create_message(
            source_agent="voter",
            event_type=EventType.SIGNAL_DETECTED,
            payload={},
            symbol="AAPL",
        )
        asyncio.run(bus.publish(msg2))

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].symbol, "AAPL")

    def test_get_result(self):
        """Test getting stored result."""
        bus = get_agent_bus()

        msg = create_message(
            source_agent="voter",
            event_type=EventType.VOTING_COMPLETE,
            payload={"action": "BUY"},
        )
        asyncio.run(bus.publish(msg))

        result = bus.get_result("voter", EventType.VOTING_COMPLETE)
        self.assertIsNotNone(result)
        self.assertEqual(result.payload["action"], "BUY")

    def test_get_history(self):
        """Test getting message history."""
        bus = get_agent_bus()

        # Publish multiple messages
        for i in range(3):
            msg = create_message(
                source_agent=f"agent_{i}",
                event_type=EventType.SIGNAL_DETECTED,
                payload={"index": i},
            )
            asyncio.run(bus.publish(msg))

        history = bus.get_history(limit=10)
        self.assertEqual(len(history), 3)
        # Newest first
        self.assertEqual(history[0].payload["index"], 2)

    def test_get_history_filtered(self):
        """Test filtered history retrieval."""
        bus = get_agent_bus()

        # Publish different event types
        msg1 = create_message("agent", EventType.SIGNAL_DETECTED, {})
        msg2 = create_message("agent", EventType.TRADE_EXECUTED, {})
        asyncio.run(bus.publish(msg1))
        asyncio.run(bus.publish(msg2))

        # Filter by event type
        history = bus.get_history(event_type=EventType.SIGNAL_DETECTED)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].get_event_key(), "signal_detected")

    def test_get_trade_history(self):
        """Test trade-specific history retrieval."""
        bus = get_agent_bus()

        # Publish trade and non-trade events
        msg1 = create_message("voter", EventType.SIGNAL_DETECTED, {}, symbol="AAPL")
        msg2 = create_message("executor", EventType.TRADE_EXECUTED, {}, symbol="AAPL")
        msg3 = create_message("executor", EventType.POSITION_OPENED, {}, symbol="AAPL")
        asyncio.run(bus.publish(msg1))
        asyncio.run(bus.publish(msg2))
        asyncio.run(bus.publish(msg3))

        trade_history = bus.get_trade_history(symbol="AAPL")
        # Should only include trade-related events
        self.assertEqual(len(trade_history), 2)

    def test_clear_results(self):
        """Test clearing stored results."""
        bus = get_agent_bus()

        msg = create_message("agent", EventType.CUSTOM, {})
        asyncio.run(bus.publish(msg))

        self.assertIsNotNone(bus.get_result("agent", EventType.CUSTOM))

        cleared = bus.clear_results()
        self.assertGreaterEqual(cleared, 1)
        self.assertIsNone(bus.get_result("agent", EventType.CUSTOM))

    def test_get_stats(self):
        """Test bus statistics."""
        bus = get_agent_bus()

        bus.subscribe("agent1", EventType.SIGNAL_DETECTED, lambda m: None)
        bus.subscribe("agent2", EventType.TRADE_EXECUTED, lambda m: None)

        msg = create_message("test", EventType.CUSTOM, {})
        asyncio.run(bus.publish(msg))

        stats = bus.get_stats()
        self.assertEqual(stats["total_subscriptions"], 2)
        self.assertGreaterEqual(stats["history_size"], 1)

    def test_reset(self):
        """Test bus reset."""
        bus = get_agent_bus()

        bus.subscribe("agent", EventType.SIGNAL_DETECTED, lambda m: None)
        msg = create_message("test", EventType.CUSTOM, {})
        asyncio.run(bus.publish(msg))

        bus.reset()
        stats = bus.get_stats()

        self.assertEqual(stats["total_subscriptions"], 0)
        self.assertEqual(stats["stored_results"], 0)
        self.assertEqual(stats["history_size"], 0)


class TestConvenienceFunctions(unittest.TestCase):
    """Test module-level convenience functions."""

    def setUp(self):
        """Reset bus before each test."""
        bus = get_agent_bus()
        bus.reset()

    def test_create_message(self):
        """Test create_message convenience function."""
        msg = create_message(
            source_agent="test",
            event_type=EventType.SIGNAL_DETECTED,
            payload={"data": "value"},
            symbol="AAPL",
            priority=5,
        )
        self.assertEqual(msg.source_agent, "test")
        self.assertEqual(msg.symbol, "AAPL")
        self.assertEqual(msg.priority, 5)

    def test_publish_result(self):
        """Test publish_result convenience function."""
        bus = get_agent_bus()
        received = []

        bus.subscribe("listener", EventType.TRADE_EXECUTED, lambda m: received.append(m))

        notified = asyncio.run(
            publish_result(
                source_agent="executor",
                event_type=EventType.TRADE_EXECUTED,
                payload={"order_id": "123"},
                symbol="AAPL",
            )
        )

        self.assertEqual(notified, 1)
        self.assertEqual(received[0].symbol, "AAPL")


class TestAsyncOperations(unittest.TestCase):
    """Test async operations."""

    def setUp(self):
        """Reset bus before each test."""
        bus = get_agent_bus()
        bus.reset()

    def test_wait_for_result_immediate(self):
        """Test waiting for result that's already available."""
        bus = get_agent_bus()

        # Publish first
        msg = create_message("voter", EventType.VOTING_COMPLETE, {"action": "BUY"})
        asyncio.run(bus.publish(msg))

        # Wait should return immediately
        async def test():
            result = await bus.wait_for_result("voter", EventType.VOTING_COMPLETE, timeout=1.0)
            return result

        result = asyncio.run(test())
        self.assertIsNotNone(result)
        self.assertEqual(result.payload["action"], "BUY")

    def test_wait_for_result_timeout(self):
        """Test waiting for result that times out."""
        bus = get_agent_bus()

        async def test():
            result = await bus.wait_for_result("nonexistent", EventType.CUSTOM, timeout=0.1)
            return result

        result = asyncio.run(test())
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
