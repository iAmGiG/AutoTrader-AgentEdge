import pytest

from src.agents.strategy_agent import StrategyAgent


def test_simple_flow():
    strat = StrategyAgent()
    aggregated = {
        "technical": {"macd_yest": -1.0, "macd_today": -0.5},
        "sentiment": {"score": 0.2},
    }
    decision = strat.decide_trade(aggregated, price=100.0, trade_date="2025-01-01")
    assert decision["action"] in {"BUY", "SELL", "HOLD"}
