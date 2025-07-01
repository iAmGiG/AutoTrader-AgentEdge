import pandas as pd
import pytest

from src.tools.data_sources.market.market_data_tool import MarketDataTool
from src.tools.data_sources.alpha_vantage_tool import AlphaVantageTool
from src.tools.data_sources.market.yahoo_finance_tool import YahooFinanceTool
from src.tools.data_sources.market.fmp_tool import FMPTool
from src.tools.data_sources.market.nasdaq_data_link_tool import NasdaqDataLinkTool


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


def test_alpha_fallback_to_fmp(monkeypatch):
    """Alpha Vantage failure triggers FMP fallback."""

    def mock_yahoo_fail(self, symbol, start, end):
        raise Exception("Rate limit")

    def mock_alpha_fail(self, symbol, start, end):
        raise Exception("API down")

    idx = pd.to_datetime(["2023-01-02"])
    sample = pd.DataFrame({"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [200]}, index=idx)

    def mock_fmp_success(self, symbol, start, end):
        return sample

    monkeypatch.setattr(YahooFinanceTool, "fetch_stock_data", mock_yahoo_fail)
    monkeypatch.setattr(AlphaVantageTool, "fetch_stock_data", mock_alpha_fail)
    monkeypatch.setattr(FMPTool, "fetch_stock_data", mock_fmp_success)

    tool = MarketDataTool({"data_source": "yahoo"})
    df = tool.fetch_market_data("AAPL", "2023-01-01", "2023-01-02")
    assert not df.empty
    assert df.iloc[0]["Open"] == 2.0


def test_fmp_fallback_to_nasdaq(monkeypatch):
    """FMP failure triggers Nasdaq Data Link fallback."""

    def mock_yahoo_fail(self, symbol, start, end):
        return pd.DataFrame()

    def mock_alpha_fail(self, symbol, start, end):
        return pd.DataFrame()

    def mock_fmp_fail(self, symbol, start, end):
        return pd.DataFrame()

    idx = pd.to_datetime(["2023-01-03"])
    sample = pd.DataFrame({"Open": [3.0], "High": [3.0], "Low": [3.0], "Close": [3.0], "Volume": [300]}, index=idx)

    def mock_nasdaq_success(self, symbol, start, end):
        return sample

    monkeypatch.setattr(YahooFinanceTool, "fetch_stock_data", mock_yahoo_fail)
    monkeypatch.setattr(AlphaVantageTool, "fetch_stock_data", mock_alpha_fail)
    monkeypatch.setattr(FMPTool, "fetch_stock_data", mock_fmp_fail)
    monkeypatch.setattr(NasdaqDataLinkTool, "fetch_stock_data", mock_nasdaq_success)

    tool = MarketDataTool({"data_source": "yahoo"})
    df = tool.fetch_market_data("AAPL", "2023-01-01", "2023-01-03")
    assert not df.empty
    assert df.iloc[0]["Open"] == 3.0
