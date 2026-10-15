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
    monkeypatch.setattr(market_hours, "_CALENDAR_DOWN_UNTIL", 0.0)


@pytest.fixture(autouse=True)
def no_broker_snapshot_cache(monkeypatch):
    """Keep BrokerStateCache from writing snapshots to the real .cache/trading_data.db."""
    from src.trading.state import broker_state_cache

    monkeypatch.setattr(broker_state_cache, "_unified_cache", False)


@pytest.fixture(autouse=True)
def fresh_ranked_voter_manager(monkeypatch):
    """Drop the shared RankedVoterManager so it can't keep an earlier test's state dir."""
    from src.core import ranked_voter_config

    monkeypatch.setattr(ranked_voter_config, "_manager", None)
