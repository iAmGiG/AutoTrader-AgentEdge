"""Shared fixtures for unit tests."""

import pytest

from src.utils.state_paths import STATE_DIR_ENV


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    """Point every state manager at a temporary state dir.

    TradingModeManager, the alerts/GTT/scheduler/portfolio managers and DBBackupManager
    default to <repo>/state/user.db. Without this, tests that construct them overwrite the
    user's saved trading mode and other state.
    """
    state_dir = tmp_path / "state"
    monkeypatch.setenv(STATE_DIR_ENV, str(state_dir))
    return state_dir


@pytest.fixture(autouse=True)
def offline_market_calendar(monkeypatch):
    """Answer market-hours questions from the NYSE rules, not Alpaca's calendar API.

    Keeps unit tests offline and deterministic; tests of the API path install their own
    fake client.
    """
    from src.utils import market_hours

    monkeypatch.setattr(market_hours, "_CALENDAR_CLIENT", None)
    monkeypatch.setattr(market_hours, "_CALENDAR_CACHE", {})
