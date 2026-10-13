"""Broker market_hours facade keeps the dict-returning is_market_hours (fixes the 66cc899 facade)."""

from datetime import datetime, time

import pytest
import pytz

import src.trading.broker.market_hours as mh

ET = pytz.timezone("America/New_York")


def _install(monkeypatch, now: datetime, status: dict):
    monkeypatch.setattr(mh, "get_datetime_now", lambda tz=None: ET.localize(now))
    monkeypatch.setattr(mh, "get_market_status_detailed", lambda: status)


def _trading(session, is_open):
    return {
        "is_open": is_open,
        "current_session": session,
        "hours": (time(9, 30), time(16, 0)),
        "is_trading_day": True,
        "current_time_et": "x",
    }


def test_package_imports():
    import src.trading  # noqa: F401  (failed before: broker/__init__ imported a missing name)
    from src.trading.broker import (is_market_hours,  # noqa: F401
                                    validate_market_hours)


def test_regular_session_open(monkeypatch):
    _install(monkeypatch, datetime(2026, 10, 13, 11, 0), _trading("market", True))
    r = mh.is_market_hours()
    assert r["is_open"] is True and r["session"] == "regular"
    assert r["hours_desc"] == "9:30 AM - 4:00 PM ET"
    assert r["extended_hours"] is False


def test_extended_hours_premarket(monkeypatch):
    _install(monkeypatch, datetime(2026, 10, 13, 7, 0), _trading("pre-market", False))
    assert mh.is_market_hours(extended_hours=False)["is_open"] is False
    r = mh.is_market_hours(extended_hours=True)
    assert r["is_open"] is True and r["session"] == "extended"


def test_extended_hours_overnight_closed(monkeypatch):
    _install(monkeypatch, datetime(2026, 10, 13, 2, 0), _trading("pre-market", False))
    assert mh.is_market_hours(extended_hours=True)["is_open"] is False


def test_holiday_closed_even_extended(monkeypatch):
    status = {
        "is_open": False,
        "current_session": "closed",
        "hours": (None, None),
        "is_trading_day": False,
        "current_time_et": "x",
    }
    _install(monkeypatch, datetime(2026, 11, 26, 11, 0), status)
    assert mh.is_market_hours()["is_open"] is False
    assert mh.is_market_hours(extended_hours=True)["is_open"] is False


def test_error_passes_through(monkeypatch):
    status = {"is_open": True, "current_session": "unknown", "hours": (None, None), "error": "boom"}
    _install(monkeypatch, datetime(2026, 10, 13, 11, 0), status)
    r = mh.is_market_hours()
    assert r["is_open"] is True and r["error"] == "boom"


@pytest.mark.parametrize("extended", [False, True])
def test_dict_keys(monkeypatch, extended):
    _install(monkeypatch, datetime(2026, 10, 13, 11, 0), _trading("market", True))
    keys = set(mh.is_market_hours(extended_hours=extended))
    assert {
        "is_open",
        "session",
        "current_session",
        "current_time_et",
        "is_weekday",
        "hours_desc",
        "extended_hours",
    } <= keys
