"""
VotingSignal: VoterAgent's MACD+RSI signal without the agent framework (#606).

The golden values below come from VoterAgent before the signal was moved out of it
(development at f9fc63a); the move must not change a single number.
"""

import subprocess
import sys
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.autogen_agents.agents.voter_agent import VoterAgent
from src.trading.instruments.voting_signal import VotingSignal


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
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)

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
