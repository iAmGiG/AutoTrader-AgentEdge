import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.strategy_agent import StrategyAgent


def test_pipeline_runs():
    strat = StrategyAgent()
    aggregated = {
        "technical": {"macd_yest": -1.0, "macd_today": -0.5},
        "sentiment": {"score": 0.2},
    }
    dec = strat.decide_trade(aggregated, price=100.0, trade_date="2025-05-01")
    assert dec["action"] in {"BUY", "SELL", "HOLD"}
