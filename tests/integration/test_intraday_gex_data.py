"""
Integration tests for intraday GEX validation data access (#530).

Verifies OHLC data and GEX total_gex are available for the test period.
Requires PostgreSQL on localhost:5432 with gex_options database.
"""

import pytest

from src.backtesting.research_backtester import ResearchBacktester

pytestmark = pytest.mark.db


class TestIntradayDataAccess:
    """Verify data needed for intraday GEX analysis is available."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.bt = ResearchBacktester(initial_capital=100_000)
        yield
        self.bt.close()

    def test_ohlc_data_available(self):
        """SPY OHLC data should be available for 2021-2023."""
        ohlc = self.bt.fetch_equity_prices(["SPY"], "2021-01-04", "2023-12-29")
        assert len(ohlc) > 700, f"Expected 700+ rows, got {len(ohlc)}"
        for col in ["open", "high", "low", "close"]:
            assert col in ohlc.columns, f"Missing column: {col}"

    def test_gex_data_available(self):
        """GEX total_gex should be available for SPY."""
        conn = self.bt._get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM options_daily_summary
            WHERE symbol = 'SPY'
              AND trading_date BETWEEN '2021-01-04' AND '2023-12-29'
              AND total_gex IS NOT NULL
            """,
        )
        count = cur.fetchone()[0]
        assert count > 500, f"Expected 500+ GEX rows, got {count}"

    def test_open_close_differ(self):
        """Open and close should differ (not identical columns)."""
        ohlc = self.bt.fetch_equity_prices(["SPY"], "2022-01-03", "2022-12-30")
        spy = ohlc[ohlc["symbol"] == "SPY"]
        # At least some days should have different open/close
        differ = (spy["open"] != spy["close"]).sum()
        assert differ > 200, f"Open == close on too many days ({differ} differ)"

    def test_multiple_symbols_available(self):
        """QQQ and IWM should also have OHLC data."""
        for sym in ["QQQ", "IWM"]:
            ohlc = self.bt.fetch_equity_prices([sym], "2021-01-04", "2023-12-29")
            assert len(ohlc) > 500, f"{sym}: Expected 500+ rows, got {len(ohlc)}"
