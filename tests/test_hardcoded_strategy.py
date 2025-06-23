import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_pipeline_runs():
    from src.agents.coordinator_agent import CoordinatorAgent
    from src.agents.strategy_agent import StrategyAgent

    coord = CoordinatorAgent(); strat = StrategyAgent()
    for _ in range(5):
        sigs = coord.get_signals("2025-05-01", "AAPL")
        assert sigs["ok"]
        dec = strat.decide_trade(sigs)
        assert dec["action"] in {"BUY", "SELL", "HOLD"}
