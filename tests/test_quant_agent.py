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


def test_process_tool_result_rich_dict():
    agent = QuantitativeAgent()
    df = pd.DataFrame(
        {
            "Open": [1, 2, 3, 4],
            "High": [1, 2, 3, 4],
            "Low": [1, 1, 2, 3],
            "Close": [1, 2, 3, 4],
            "Volume": [100] * 4,
        }
    )
    result = agent.process_tool_result("fetch_market_data", df, {})
    assert isinstance(result["latest_row"], dict)
    assert isinstance(result["go_flag"], bool)
    assert isinstance(result["go_rationale"], list)
    assert isinstance(result["risk"], dict)
    assert "sharpe" in result["risk"] and "drawdown" in result["risk"]
    assert isinstance(result["events"], dict)
    assert isinstance(result["spark"], str)
    assert isinstance(result["timestamp"], str)


def test_avwap_anchor_in_result():
    agent = QuantitativeAgent()
    agent.last_query = {"anchor": "2025-01-02"}
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame(
        {
            "Open": [1, 2, 3],
            "High": [1, 2, 3],
            "Low": [1, 1, 2],
            "Close": [1, 2, 3],
            "Volume": [100, 100, 100],
        },
        index=idx,
    )
    result = agent.process_tool_result(
        "fetch_market_data", df, {"indicators": ["avwap"]}
    )
    assert result["anchor_ts"].startswith("2025-01-02")


def test_preprocess_extends_for_indicators():
    agent = QuantitativeAgent()
    parsed = agent.preprocess_message("AAPL last 5 days with rsi(14)")
    start = pd.to_datetime(parsed["start_date"])
    end = pd.to_datetime(parsed["end_date"])
    diff = (end - start).days
    assert diff >= 14
