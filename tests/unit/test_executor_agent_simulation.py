"""Simulated execution never fills at a guessed price."""

import pytest

from src.autogen_agents.agents.executor_agent import ExecutorAgent


def test_no_price_means_no_simulated_fill():
    agent = object.__new__(ExecutorAgent)  # only the simulation method is exercised
    agent._get_current_price = lambda symbol: None
    agent.available_capital, agent.positions = 10_000.0, {}

    with pytest.raises(ValueError, match="No price available for SOXL"):
        agent._simulate_execution("SOXL", "buy", 10, "market")

    assert agent.available_capital == 10_000.0
    assert agent.positions == {}
