"""date_utils business-day helpers follow the NYSE calendar (holidays, not just weekends)."""

from datetime import date

import pytest

from src.utils.date_utils import (add_business_days, date_range_trading_days,
                                  is_business_day, next_business_day)
from src.utils.market_hours import is_nyse_trading_day, nyse_closures


@pytest.mark.parametrize(
    "day, trading",
    [
        ("2026-10-15", True),  # Thursday
        ("2026-10-17", False),  # Saturday
        ("2026-11-26", False),  # Thanksgiving
        ("2026-11-27", True),  # early close, still a trading day
        ("2026-12-25", False),  # Christmas
        ("2027-06-18", False),  # Juneteenth (Saturday) observed on Friday
        ("2021-06-18", True),  # before Juneteenth became an NYSE holiday
    ],
)
def test_business_days_skip_nyse_holidays(day, trading):
    assert is_business_day(day) is trading
    assert is_nyse_trading_day(date.fromisoformat(day)) is trading


def test_adding_business_days_steps_over_holidays():
    assert next_business_day("2026-11-25") == "2026-11-27"  # over Thanksgiving
    assert add_business_days("2026-12-24", 1) == "2026-12-28"  # over Christmas and the weekend
    assert add_business_days("2026-01-02", -1) == "2025-12-31"  # back over New Year's Day


def test_from_a_closed_day_the_next_trading_day_is_one_day_on():
    assert next_business_day("2026-10-17") == "2026-10-19"  # Saturday -> Monday
    assert next_business_day("2026-11-26") == "2026-11-27"  # Thanksgiving -> Friday
    assert add_business_days("2026-11-26", -1) == "2026-11-25"
    assert add_business_days("2026-10-17", 0) == "2026-10-19"  # rolls forward


@pytest.mark.parametrize("day", ["2012-10-29", "2012-10-30", "2018-12-05", "2025-01-09"])
def test_past_one_off_closures_are_not_trading_days(day):
    assert is_business_day(day) is False
    assert day not in date_range_trading_days("2012-10-01", "2025-01-31")


@pytest.fixture
def fresh_offsets():
    """Business-day offsets are cached by year span; don't reuse ones built with other closures."""
    from src.utils import date_utils

    date_utils._nyse_business_day.cache_clear()
    yield
    date_utils._nyse_business_day.cache_clear()


def test_configured_closures_may_be_unquoted_yaml_dates(monkeypatch, fresh_offsets):
    from src.utils import market_hours

    config = {"holidays": {"enabled": True, "fixed_holidays": [date(2026, 10, 16)]}}
    monkeypatch.setattr(market_hours, "_load_market_config", lambda: config)

    assert is_business_day("2026-10-16") is False
    assert "2026-10-16" not in date_range_trading_days("2026-10-15", "2026-10-19")


def test_a_long_step_still_counts_only_trading_days():
    assert (
        add_business_days("2026-01-02", 252)
        == date_range_trading_days("2026-01-02", "2027-01-10")[252]
    )


def test_trading_day_ranges_leave_out_holidays():
    assert date_range_trading_days("2026-11-24", "2026-12-01") == [
        "2026-11-24",
        "2026-11-25",
        "2026-11-27",
        "2026-11-30",
        "2026-12-01",
    ]


def test_closures_are_weekday_holidays_in_range():
    assert nyse_closures(date(2026, 11, 1), date(2026, 12, 31)) == {
        date(2026, 11, 26),
        date(2026, 12, 25),
    }
