"""Research prices are split-adjusted by default (equity_prices_daily stores raw prices)."""

import pytest

from src.backtesting.research_backtester import ResearchBacktester

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def bt():
    backtester = ResearchBacktester()
    yield backtester
    backtester.close()


@pytest.mark.parametrize(
    "symbol, start, end, split_day",
    [
        ("AAPL", "2020-08-26", "2020-09-02", "2020-08-31"),  # 4-for-1
        ("XLK", "2025-12-01", "2025-12-10", "2025-12-05"),  # 2-for-1
    ],
)
def test_split_day_is_not_a_fake_move(bt, symbol, start, end, split_day):
    adjusted = bt.get_close_prices([symbol], start, end)[symbol]
    raw = bt.fetch_equity_prices([symbol], start, end, adjust_splits=False)
    raw_close = raw.set_index("trading_date")["close"].astype(float)

    assert raw_close.pct_change().loc[split_day] < -0.4  # the table's raw drop
    assert abs(adjusted.pct_change().loc[split_day]) < 0.1


def test_split_after_the_window_is_not_applied(bt):
    # AAPL's 2020-08-31 split is after this window: prices stay at their raw scale
    adjusted = bt.get_close_prices(["AAPL"], "2020-08-03", "2020-08-28")["AAPL"]
    raw = bt.fetch_equity_prices(["AAPL"], "2020-08-03", "2020-08-28", adjust_splits=False)

    assert adjusted.iloc[-1] == pytest.approx(float(raw["close"].iloc[-1]))
