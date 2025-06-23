import pandas as pd
import pytest

from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.tools.data_sources.alpha_vantage_tool import AlphaVantageTool
from src.tools.data_sources.market.yahoo_finance_tool import YahooFinanceTool


def test_yahoo_fallback_to_alpha(monkeypatch):
    """Ensure MarketDataTool falls back to Alpha Vantage when Yahoo fails."""

    def mock_yahoo_fail(self, symbol, start, end):
        raise Exception("Too Many Requests")

    idx = pd.to_datetime(["2023-01-02"])
    sample = pd.DataFrame(
        {
            "Open": [1.0],
            "High": [1.0],
            "Low": [1.0],
            "Close": [1.0],
            "Volume": [100],
        },
        index=idx,
    )

    def mock_alpha_success(self, symbol, start, end):
        return sample

    monkeypatch.setattr(YahooFinanceTool, "fetch_stock_data", mock_yahoo_fail)
    monkeypatch.setattr(AlphaVantageTool, "fetch_stock_data", mock_alpha_success)

    tool = MarketDataTool({"data_source": "yahoo"})
    df = tool.fetch_market_data("AAPL", "2023-01-01", "2023-01-02")
    assert not df.empty
    assert list(df.columns) == list(sample.columns)
    assert df.iloc[0]["Open"] == 1.0
