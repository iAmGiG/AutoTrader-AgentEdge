import pandas as pd
from src.agents.quantitative_agent import QuantitativeAgent


def test_preprocess_macd():
    agent = QuantitativeAgent()
    parsed = agent.preprocess_message("Show me MACD for TSLA")
    names = [i.split("(")[0] for i in parsed["indicators"]]
    assert "macd" in names


def test_process_tool_result_macd():
    agent = QuantitativeAgent()
    df = pd.DataFrame(
        {
            "Open": [1, 2, 3, 4, 5, 6],
            "High": [1, 2, 3, 4, 5, 6],
            "Low": [1, 1, 2, 3, 4, 5],
            "Close": [1, 2, 3, 4, 5, 6],
            "Volume": [100] * 6,
        }
    )
    result = agent.process_tool_result(
        "fetch_market_data", df, {"indicators": ["macd"]}
    )
    assert "MACD_line" in result["latest_row"]


def test_process_tool_result_spark():
    agent = QuantitativeAgent()
    df = pd.DataFrame(
        {
            "Open": range(1, 9),
            "High": range(1, 9),
            "Low": range(1, 9),
            "Close": range(1, 9),
            "Volume": [100] * 8,
        }
    )
    result = agent.process_tool_result("fetch_market_data", df, {})
    assert result["spark"] == "▁▂▃▄▅▆▇█"
