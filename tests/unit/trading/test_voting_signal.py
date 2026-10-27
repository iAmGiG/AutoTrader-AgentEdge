"""
VotingSignal: VoterAgent's MACD+RSI signal without the agent framework (#606).

The golden values below come from VoterAgent before the signal was moved out of it
(development at f9fc63a); the move must not change a single number.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.autogen_agents.agents.voter_agent import VoterAgent
from src.autogen_agents.core import base_agent
from src.trading.instruments.voting_signal import VotingSignal

REPO = Path(__file__).resolve().parents[3]


def _series(seed):
    """The synthetic series the golden values were computed on."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(30, 260))
    drift = rng.normal(0, 0.002)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, 0.015, n)))
    col = "close" if seed % 2 else "Close"
    return pd.DataFrame({col: close}, index=pd.bdate_range("2024-01-02", periods=n))


GOLDEN = [
    ("evaluate_ranked_voting", 0, "BUY", 0.7, 0.5, "WEAK"),
    ("evaluate_ranked_voting", 1, "HOLD", 0.0, 0.0, "CONFLICT"),
    ("evaluate_ranked_voting", 4, "SELL", 0.7, 0.5, "WEAK"),
    ("evaluate_voting", 0, "BUY", 0.736982745480242, 0.5, "WEAK"),
    ("evaluate_voting", 1, "HOLD", 0.2, 0.0, "CONFLICT"),
    ("evaluate_voting", 4, "SELL", 0.672028271408902, 0.5, "WEAK"),
]


@pytest.mark.parametrize("method,seed,action,confidence,size,signal_type", GOLDEN)
def test_decisions_match_the_voter_agent_before_the_move(
    method, seed, action, confidence, size, signal_type
):
    result = getattr(VotingSignal(), method)(f"S{seed}", _series(seed), False)

    assert (result["action"], result["position_size"], result["signal_type"]) == (
        action,
        size,
        signal_type,
    )
    assert result["confidence"] == pytest.approx(confidence, abs=1e-12)


def test_too_little_data_is_a_hold():
    result = VotingSignal().evaluate_voting("S23", _series(23))  # 38 points < 42

    assert result["action"] == "HOLD"
    assert "Insufficient data (38 < 42)" in result["reasoning"]


def test_the_signal_loads_no_agent_framework_or_llm_client():
    code = (
        "import sys; import src.trading.instruments.voting_signal; "
        "print(sorted({m.split('.')[0] for m in sys.modules "
        "if m.startswith(('autogen', 'openai', 'agent_framework'))}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=REPO
    )

    assert out.stdout.strip() == "[]"


def _agent():
    """A VoterAgent without BaseAgent's LLM client: only the parts these tests use."""
    agent = object.__new__(VoterAgent)
    agent.signal = VotingSignal()
    agent._publish_events = True
    agent._publish_voting_result = MagicMock()
    return agent


@pytest.mark.parametrize("method", ["evaluate_voting", "evaluate_ranked_voting"])
def test_the_agent_returns_the_signals_decision(method):
    agent = _agent()

    for seed in (0, 1, 4):
        assert getattr(agent, method)("S", _series(seed), True) == getattr(VotingSignal(), method)(
            "S", _series(seed), True
        )


def test_the_agent_publishes_buys_and_sells_only():
    agent = _agent()

    agent.evaluate_voting("BUY", _series(0))
    agent.evaluate_voting("HOLD", _series(1))
    agent.evaluate_voting("SELL", _series(4))

    published = [c.args[0] for c in agent._publish_voting_result.call_args_list]
    assert published == ["BUY", "SELL"]


def test_agent_parameters_are_the_signals():
    agent = _agent()

    agent.reconfigure(timeframe="4h", macd_params={"fast": 8})
    agent.rsi_params = {"period": 7, "oversold": 25, "overbought": 75}

    assert agent.signal.timeframe == "4h"
    assert agent.signal.macd_params["fast"] == 8
    assert agent.signal.rsi_params["period"] == 7
    assert agent.current_config["timeframe"] == "4h"


def test_a_decision_keeps_the_parameters_it_was_computed_with():
    signal = VotingSignal()
    result = signal.evaluate_voting("S0", _series(0))

    signal.reconfigure(timeframe="4h", macd_params={"fast": 8})

    assert result["parameters_used"]["timeframe"] == "1d"
    assert result["parameters_used"]["macd"]["fast"] == 13


def test_a_callers_parameter_dict_is_not_changed():
    shared = {"fast": 13, "slow": 34, "signal": 8}
    first, second = VotingSignal(macd_params=shared), VotingSignal(macd_params=shared)

    first.reconfigure(macd_params={"fast": 8})

    assert shared["fast"] == 13
    assert second.macd_params["fast"] == 13


def test_reset_restores_every_parameter_including_the_timeframe():
    signal = VotingSignal(use_config_file=False)
    signal.reconfigure(timeframe="4h", rsi_params={"period": 7})

    signal.reset_to_defaults(use_config_file=False)

    assert signal.timeframe == "1d"
    assert signal.rsi_params["period"] == 14
    assert signal.current_config["timeframe"] == "1d"


@pytest.mark.parametrize("use_config_file", [True, False])
def test_the_agent_constructor_wires_its_signal(monkeypatch, use_config_file):
    """The real VoterAgent.__init__, with only BaseAgent's LLM client set-up skipped."""
    monkeypatch.setattr(base_agent.BaseAgent, "__init__", lambda self, *args, **kwargs: None)

    agent = VoterAgent(name="voter", timeframe="4h", use_config_file=use_config_file)

    assert isinstance(agent.signal, VotingSignal)
    assert agent.timeframe == "4h" and agent.current_config["timeframe"] == "4h"
    if use_config_file:
        assert agent.config is agent.signal.config is not None
    else:
        assert agent.signal.config is None and not hasattr(agent, "config")
    assert agent.evaluate_voting("S0", _series(0))["action"] == "BUY"
