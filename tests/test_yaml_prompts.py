#!/usr/bin/env python3
"""
Validation tests for YAML prompt loading
Tests for issue #328: YAML Optimization
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.agent_utils import load_agent_config


class TestYAMLPromptLoading(unittest.TestCase):
    """Test suite for YAML prompt loading functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.config_file = Path(__file__).parent.parent / "config" / "agent_prompts.yaml"

    def test_yaml_file_exists(self):
        """Test that the agent_prompts.yaml file exists."""
        self.assertTrue(
            self.config_file.exists(), f"YAML config file not found at {self.config_file}"
        )

    def test_load_agents_section(self):
        """Test loading the agents section."""
        agents = load_agent_config("agents")
        self.assertIsInstance(agents, dict, "Agents config should be a dictionary")
        self.assertIn("voter_agent", agents, "voter_agent should be in agents config")

    def test_voter_agent_prompt(self):
        """Test voter agent system prompt."""
        agents = load_agent_config("agents")
        voter_config = agents.get("voter_agent", {})

        self.assertIn("system_prompt", voter_config, "voter_agent should have a system_prompt")

        prompt = voter_config["system_prompt"]
        self.assertIsInstance(prompt, str, "system_prompt should be a string")
        self.assertGreater(len(prompt), 50, "system_prompt should not be empty")

        # Check that prompt contains expected placeholders
        self.assertIn("{macd}", prompt, "Prompt should contain {macd} placeholder")
        self.assertIn("{rsi}", prompt, "Prompt should contain {rsi} placeholder")
        self.assertIn("{thresholds}", prompt, "Prompt should contain {thresholds} placeholder")

    def test_load_tools_section(self):
        """Test loading the tools section."""
        tools = load_agent_config("tools")
        self.assertIsInstance(tools, dict, "Tools config should be a dictionary")

        # Check for expected tools
        expected_tools = [
            "unified_market_data",
            "vxx_volatility_data",
            "hierarchical_news",
            "market_context",
        ]
        for tool in expected_tools:
            self.assertIn(tool, tools, f"{tool} should be in tools config")

    def test_tool_descriptions(self):
        """Test that tool descriptions are properly loaded."""
        tools = load_agent_config("tools")

        # Check unified_market_data tool
        unified_tool = tools.get("unified_market_data", {})
        self.assertIn("description", unified_tool, "unified_market_data should have a description")
        self.assertGreater(
            len(unified_tool["description"]), 20, "Tool description should not be empty"
        )

    def test_load_interface_section(self):
        """Test loading the interface section."""
        interface = load_agent_config("interface")
        self.assertIsInstance(interface, dict, "Interface config should be a dictionary")
        self.assertIn("llm_assistant", interface, "llm_assistant should be in interface config")

    def test_llm_assistant_help_text(self):
        """Test LLM assistant help text."""
        interface = load_agent_config("interface")
        llm_config = interface.get("llm_assistant", {})

        self.assertIn("help_text", llm_config, "llm_assistant should have help_text")

        help_text = llm_config["help_text"]
        self.assertIsInstance(help_text, str, "help_text should be a string")
        self.assertGreater(len(help_text), 50, "help_text should not be empty")

        # Check that help text contains expected commands
        self.assertIn("add", help_text.lower(), "Help text should mention 'add' command")
        self.assertIn("close", help_text.lower(), "Help text should mention 'close' command")

    def test_invalid_section_returns_empty_dict(self):
        """Test that requesting invalid section returns empty dict."""
        result = load_agent_config("nonexistent_section")
        self.assertIsInstance(result, dict, "Should return dict for invalid section")
        self.assertEqual(len(result), 0, "Should return empty dict for invalid section")

    def test_market_context_tool_description(self):
        """Test market context tool description has proper format."""
        tools = load_agent_config("tools")
        market_context = tools.get("market_context", {})

        self.assertIn("description", market_context, "market_context should have a description")

        desc = market_context["description"]
        self.assertIn("SPY", desc, "Description should mention SPY")
        self.assertIn("QQQ", desc, "Description should mention QQQ")

    def test_yaml_structure_integrity(self):
        """Test overall YAML structure integrity."""
        # Try loading all main sections
        sections = ["agents", "tools", "interface"]

        for section in sections:
            config = load_agent_config(section)
            self.assertIsInstance(config, dict, f"Section '{section}' should load as dictionary")
            self.assertGreater(len(config), 0, f"Section '{section}' should not be empty")


class TestPromptUsage(unittest.TestCase):
    """Test that prompts are being used correctly in the codebase."""

    def test_voter_agent_imports_agent_utils(self):
        """Test that voter_agent.py imports agent_utils."""
        voter_agent_file = (
            Path(__file__).parent.parent / "src" / "autogen_agents" / "voter_agent.py"
        )

        with open(voter_agent_file, "r") as f:
            content = f.read()

        self.assertIn(
            "from src.utils.agent_utils import load_agent_config",
            content,
            "voter_agent.py should import load_agent_config",
        )

    def test_tools_py_imports_agent_utils(self):
        """Test that tools.py imports agent_utils."""
        tools_file = Path(__file__).parent.parent / "src" / "data_sources" / "tools.py"

        with open(tools_file, "r") as f:
            content = f.read()

        self.assertIn("load_agent_config", content, "tools.py should import load_agent_config")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
