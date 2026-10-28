"""
Market hours come from Alpaca's calendar, with NYSE rules as the offline fallback.

The expected dates below were read from Alpaca's calendar API (2022-2029). The rules
can't know one-off closures such as 2025-01-09 (national day of mourning), so that day
is left out.
"""

from datetime import date, datetime, time
from types import SimpleNamespace

import pytest

import src.utils.market_hours as mh

ALPACA_HOLIDAYS = {
    2022: "01-17 02-21 04-15 05-30 06-20 07-04 09-05 11-24 12-26",
    2023: "01-02 01-16 02-20 04-07 05-29 06-19 07-04 09-04 11-23 12-25",
    2024: "01-01 01-15 02-19 03-29 05-27 06-19 07-04 09-02 11-28 12-25",
    2025: "01-01 01-20 02-17 04-18 05-26 06-19 07-04 09-01 11-27 12-25",
    2026: "01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25",
    2027: "01-01 01-18 02-15 03-26 05-31 06-18 07-05 09-06 11-25 12-24",
    2028: "01-17 02-21 04-14 05-29 06-19 07-04 09-04 11-23 12-25",
    2029: "01-01 01-15 02-19 03-30 05-28 06-19 07-04 09-03 11-22 12-25",
}
ALPACA_EARLY_CLOSES = {
    2022: "11-25",
    2023: "07-03 11-24",
    2024: "07-03 11-29 12-24",
    2025: "07-03 11-28 12-24",
    2026: "11-27 12-24",
    2027: "11-26",
    2028: "07-03 11-24",
    2029: "07-03 11-23 12-24",
}


def _dates(year, spec):
    return {date.fromisoformat(f"{year}-{md}") for md in spec.split()}


@pytest.mark.parametrize("year", sorted(ALPACA_HOLIDAYS))
def test_rules_match_alpaca_holidays(year):
    assert mh.nyse_holidays(year) == _dates(year, ALPACA_HOLIDAYS[year])


@pytest.mark.parametrize("year", sorted(ALPACA_EARLY_CLOSES))
def test_rules_match_alpaca_early_closes(year):
    assert mh.nyse_early_closes(year) == _dates(year, ALPACA_EARLY_CLOSES[year])


def test_offline_fallback_uses_the_rules():
    # The autouse fixture leaves no calendar client
    assert mh.get_market_hours_for_date(date(2026, 11, 26))[2] is False  # Thanksgiving
    assert mh.get_market_hours_for_date(date(2026, 11, 27)) == (time(9, 30), time(13, 0), True)
    assert mh.get_market_hours_for_date(datetime(2026, 10, 14, 12, 0))[2] is True


class _FakeCalendarClient:
    def __init__(self, days=None, error=None):
        self.days, self.error, self.requests = days or {}, error, []

    def get_calendar(self, filters):
        self.requests.append(filters)
        if self.error:
            raise self.error
        day = self.days.get(filters.start)
        return [day] if day else []


def _session(day, close_hour=16, listed_as=None):
    return SimpleNamespace(
        date=listed_as or day,
        open=datetime.combine(day, time(9, 30)),
        close=datetime.combine(day, time(close_hour, 0)),
    )


def test_calendar_api_answers_and_is_cached(monkeypatch):
    early = date(2026, 12, 24)
    client = _FakeCalendarClient({early: _session(early, close_hour=13)})
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", client)

    assert mh.get_market_hours_for_date(early) == (time(9, 30), time(13, 0), True)
    assert mh.get_market_hours_for_date(early) == (time(9, 30), time(13, 0), True)
    assert mh.get_market_hours_for_date(date(2026, 12, 25))[2] is False  # no session

    assert len(client.requests) == 2  # the repeat came from the cache
    assert (client.requests[0].start, client.requests[0].end) == (early, early)


def test_calendar_api_failure_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", _FakeCalendarClient(error=ConnectionError()))

    assert mh.get_market_hours_for_date(date(2026, 11, 26))[2] is False


def test_calendar_client_uses_the_paper_keys(monkeypatch):
    class _Config:
        def get(self, key, default=None):
            return {"ALPACA_PAPER_API_KEY": "pk", "ALPACA_PAPER_SECRET": "ps"}.get(key, default)

    built = {}
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", mh._UNSET)
    monkeypatch.setattr(mh, "ConfigLoader", _Config)
    monkeypatch.setattr(mh, "TradingClient", lambda **kwargs: built.update(kwargs) or "client")

    assert mh._get_alpaca_calendar() == "client"
    assert built == {"api_key": "pk", "secret_key": "ps", "paper": True}


def test_calendar_failure_backs_off_then_retries(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(mh, "monotonic", lambda: clock["now"])
    client = _FakeCalendarClient(error=ConnectionError("down"))
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", client)

    mh.get_market_hours_for_date(date(2026, 10, 14))
    mh.get_market_hours_for_date(date(2026, 10, 15))  # within the back-off: rules only
    assert len(client.requests) == 1

    clock["now"] += mh._CALENDAR_RETRY_SECONDS + 1
    mh.get_market_hours_for_date(date(2026, 10, 16))
    assert len(client.requests) == 2


def test_client_build_failure_is_retried_after_back_off(monkeypatch):
    class _Config:
        def get(self, key, default=None):
            return {"ALPACA_PAPER_API_KEY": "pk", "ALPACA_PAPER_SECRET": "ps"}.get(key, default)

    clock = {"now": 1000.0}
    attempts = []

    def flaky_client(**kwargs):
        attempts.append(kwargs)
        if len(attempts) == 1:
            raise OSError("transient")
        return "client"

    monkeypatch.setattr(mh, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", mh._UNSET)
    monkeypatch.setattr(mh, "ConfigLoader", _Config)
    monkeypatch.setattr(mh, "TradingClient", flaky_client)

    assert mh._get_alpaca_calendar() is None
    assert mh._get_alpaca_calendar() is None  # still backing off, no new attempt
    clock["now"] += mh._CALENDAR_RETRY_SECONDS + 1
    assert mh._get_alpaca_calendar() == "client"
    assert len(attempts) == 2


# --- NYSE's own published calendar: an oracle independent of Alpaca's -------------------
# From NYSE Group's release of 2025-12-23 ("2026, 2027 and 2028 Holiday and Early Closings
# Calendar"). 2028-01-01 is a Saturday and no holiday is observed for it.
NYSE_HOLIDAYS = {
    2026: "01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25",
    2027: "01-01 01-18 02-15 03-26 05-31 06-18 07-05 09-06 11-25 12-24",
    2028: "01-17 02-21 04-14 05-29 06-19 07-04 09-04 11-23 12-25",
}
NYSE_EARLY_CLOSES = {2026: "11-27 12-24", 2027: "11-26", 2028: "07-03 11-24"}


@pytest.mark.parametrize("year", sorted(NYSE_HOLIDAYS))
def test_rules_match_nyse_published_holidays_and_early_closes(year):
    assert mh.nyse_holidays(year) == _dates(year, NYSE_HOLIDAYS[year])
    assert mh.nyse_early_closes(year) == _dates(year, NYSE_EARLY_CLOSES[year])


# --- Guards on the calendar's answer ----------------------------------------------------


@pytest.mark.parametrize(
    "day",
    [date(2026, 10, 31), date(2029, 12, 26), date(2030, 1, 2)],  # Saturday; past the data
)
def test_weekends_and_days_past_the_calendar_data_make_no_request(monkeypatch, day):
    client = _FakeCalendarClient()
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", client)

    hours = mh.get_market_hours_for_date(day)

    assert client.requests == []
    assert hours == mh._rule_based_hours(day)
    assert mh.calendar_disagreement(day) is None


def test_a_row_for_another_day_is_not_trusted(monkeypatch):
    day = date(2026, 11, 26)  # Thanksgiving; an out-of-range answer once came back as 1970
    client = _FakeCalendarClient({day: _session(day, listed_as=date(1970, 1, 2))})
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", client)

    assert mh.get_market_hours_for_date(day)[2] is False  # the rules: closed
    assert "1970-01-02" in mh.calendar_disagreement(day)
    assert mh.get_market_hours_for_date(day)[2] is False
    assert len(client.requests) == 1  # the rules' answer is cached for the process


def test_an_early_close_day_listed_until_16_00_closes_at_13_00(monkeypatch):
    day = date(2026, 11, 27)
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", _FakeCalendarClient({day: _session(day)}))

    assert mh.get_market_hours_for_date(day) == (time(9, 30), time(13, 0), True)
    assert "16:00" in mh.calendar_disagreement(day)


def test_a_session_the_rules_call_closed_is_trusted_but_noted(monkeypatch):
    day = date(2026, 11, 26)  # as if NYSE had opened on Thanksgiving
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", _FakeCalendarClient({day: _session(day)}))

    assert mh.get_market_hours_for_date(day)[2] is True
    assert "call closed" in mh.calendar_disagreement(day)


def test_agreeing_answers_note_nothing(monkeypatch):
    day = date(2026, 10, 28)
    monkeypatch.setattr(mh, "_CALENDAR_CLIENT", _FakeCalendarClient({day: _session(day)}))

    assert mh.get_market_hours_for_date(day)[2] is True
    assert mh.calendar_disagreement(day) is None


def test_an_earlier_calendar_close_on_a_full_rules_day_is_used_and_noted(monkeypatch):
    day = date(2026, 10, 28)  # as if NYSE had announced an unscheduled 13:00 close
    monkeypatch.setattr(
        mh, "_CALENDAR_CLIENT", _FakeCalendarClient({day: _session(day, close_hour=13)})
    )

    assert mh.get_market_hours_for_date(day) == (time(9, 30), time(13, 0), True)
    assert "13:00" in mh.calendar_disagreement(day)
