import pytest

from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.strategy_agent import StrategyAgent
from src.tools.date_utils import process_date_param


def test_simple_flow():
    date = process_date_param("2024-01-05")
    coord = CoordinatorAgent()
    strat = StrategyAgent()
    agg = coord.get_signals(date, "AAPL")
    dec = strat.decide_trade(agg)
    assert dec["action"] in ("BUY", "HOLD")
