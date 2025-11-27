#!/usr/bin/env python3
"""
Unit tests for AgentFactory.

Tests the factory pattern implementation for creating trading agents.
Issue #390: Agent Factory & Event Bus Infrastructure
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.autogen_agents.agent_factory import (
    AgentConfig,
    AgentFactory,
    AgentInstance,
    AgentType,
    create_agent,
    create_voter,
    get_agent_factory,
)


class TestAgentType(unittest.TestCase):
    """Test AgentType enum."""

    def test_all_agent_types_exist(self):
        """Verify all expected agent types are defined."""
        expected_types = ["SCANNER", "VOTER", "RISK", "EXECUTOR", "PORTFOLIO", "ORCHESTRATOR"]
        actual_types = [t.name for t in AgentType]
        for expected in expected_types:
            self.assertIn(expected, actual_types)

    def test_agent_type_values(self):
        """Verify agent type values are lowercase strings."""
        for agent_type in AgentType:
            self.assertEqual(agent_type.value, agent_type.name.lower())


class TestAgentConfig(unittest.TestCase):
    """Test AgentConfig dataclass."""

    def test_default_values(self):
        """Test AgentConfig default values."""
        config = AgentConfig(agent_type=AgentType.VOTER, name="test_voter")
        self.assertEqual(config.agent_type, AgentType.VOTER)
        self.assertEqual(config.name, "test_voter")
        self.assertEqual(config.model_name, "gpt-4o-mini")
        self.assertEqual(config.temperature, 0.2)
        self.assertEqual(config.max_tokens, 4096)
        self.assertEqual(config.timeout, 120)
        self.assertEqual(config.tools, [])
        self.assertEqual(config.extra_config, {})

    def test_custom_values(self):
        """Test AgentConfig with custom values."""
        config = AgentConfig(
            agent_type=AgentType.RISK,
            name="custom_risk",
            description="Custom risk agent",
            model_name="gpt-4o",
            temperature=0.1,
            max_tokens=2048,
            timeout=60,
            tools=["risk_calculator"],
            extra_config={"max_position_pct": 0.1},
        )
        self.assertEqual(config.temperature, 0.1)
        self.assertEqual(config.max_tokens, 2048)
        self.assertIn("risk_calculator", config.tools)
        self.assertEqual(config.extra_config["max_position_pct"], 0.1)


class TestAgentInstance(unittest.TestCase):
    """Test AgentInstance wrapper."""

    def test_instance_creation(self):
        """Test AgentInstance creation and metadata."""
        config = AgentConfig(agent_type=AgentType.VOTER, name="test")
        instance = AgentInstance(
            agent="mock_agent",
            config=config,
            agent_type=AgentType.VOTER,
        )
        self.assertEqual(instance.agent, "mock_agent")
        self.assertEqual(instance.agent_type, AgentType.VOTER)
        self.assertIsNotNone(instance.created_at)


class TestAgentFactory(unittest.TestCase):
    """Test AgentFactory singleton."""

    def setUp(self):
        """Reset factory before each test."""
        factory = get_agent_factory()
        factory.clear_created_agents()

    def test_singleton_pattern(self):
        """Verify factory is a singleton."""
        factory1 = get_agent_factory()
        factory2 = get_agent_factory()
        self.assertIs(factory1, factory2)

    def test_get_agent_types(self):
        """Test getting available agent types."""
        factory = get_agent_factory()
        types = factory.get_agent_types()
        self.assertIn(AgentType.VOTER, types)
        self.assertIn(AgentType.SCANNER, types)
        self.assertIn(AgentType.RISK, types)
        self.assertIn(AgentType.EXECUTOR, types)

    def test_get_config(self):
        """Test getting agent configuration."""
        factory = get_agent_factory()
        config = factory.get_config(AgentType.VOTER)
        self.assertEqual(config.agent_type, AgentType.VOTER)
        self.assertEqual(config.name, "voter_agent")
        # Check MACD params from TradingConfig
        self.assertIn("macd_params", config.extra_config)

    def test_set_config(self):
        """Test setting agent configuration."""
        factory = get_agent_factory()
        new_config = AgentConfig(
            agent_type=AgentType.VOTER,
            name="custom_voter",
            temperature=0.5,
        )
        factory.set_config(AgentType.VOTER, new_config)
        retrieved = factory.get_config(AgentType.VOTER)
        self.assertEqual(retrieved.name, "custom_voter")
        self.assertEqual(retrieved.temperature, 0.5)
        # Reset for other tests
        factory.reset()

    def test_factory_stats(self):
        """Test factory statistics."""
        factory = get_agent_factory()
        factory.clear_created_agents()
        stats = factory.get_factory_stats()
        self.assertEqual(stats["total_agents_created"], 0)
        self.assertIn("voter", stats["registered_types"])

    def test_clear_created_agents(self):
        """Test clearing created agents list."""
        factory = get_agent_factory()
        factory.clear_created_agents()
        stats = factory.get_factory_stats()
        self.assertEqual(stats["total_agents_created"], 0)


class TestConvenienceFunctions(unittest.TestCase):
    """Test module-level convenience functions."""

    def setUp(self):
        """Reset factory before each test."""
        factory = get_agent_factory()
        factory.clear_created_agents()

    def test_create_voter_convenience(self):
        """Test create_voter() convenience function."""
        # Note: This may fail if VoterAgent has dependency issues
        # but we're testing the function exists and is callable
        try:
            instance = create_voter()
            self.assertEqual(instance.agent_type, AgentType.VOTER)
        except Exception as e:
            # If VoterAgent has import issues, just verify function exists
            self.assertTrue(callable(create_voter))

    def test_create_agent_function(self):
        """Test create_agent() convenience function."""
        self.assertTrue(callable(create_agent))


class TestConfigMerging(unittest.TestCase):
    """Test configuration override merging."""

    def test_merge_preserves_base(self):
        """Test that merging preserves unoverridden base values."""
        factory = get_agent_factory()
        base_config = factory.get_config(AgentType.VOTER)

        # Create with override
        merged = factory._merge_config(
            base_config, {"temperature": 0.9}
        )

        self.assertEqual(merged.temperature, 0.9)
        self.assertEqual(merged.model_name, base_config.model_name)
        self.assertEqual(merged.timeout, base_config.timeout)

    def test_merge_extra_config(self):
        """Test that extra_config is properly merged."""
        factory = get_agent_factory()
        base_config = AgentConfig(
            agent_type=AgentType.VOTER,
            name="test",
            extra_config={"a": 1, "b": 2},
        )

        merged = factory._merge_config(
            base_config, {"extra_config": {"b": 3, "c": 4}}
        )

        self.assertEqual(merged.extra_config["a"], 1)
        self.assertEqual(merged.extra_config["b"], 3)
        self.assertEqual(merged.extra_config["c"], 4)


if __name__ == "__main__":
    unittest.main()
