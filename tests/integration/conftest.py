"""
Database test fixtures for GEX Database Infrastructure integration.

Provides:
- Auto-skip hook: @pytest.mark.db tests skip when PostgreSQL is unavailable
- Session-scoped live DB fixtures (read-only)
- Mock fixtures for CI-safe unit testing

Connection: localhost:5432 / gex_options / cregan1 (trust auth)
"""

import socket
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# PostgreSQL availability probe
# ---------------------------------------------------------------------------

_PG_AVAILABLE: bool | None = None


def _pg_is_available(host: str = "localhost", port: int = 5432, timeout: float = 3.0) -> bool:
    """Probe PostgreSQL TCP port; cached for session lifetime."""
    global _PG_AVAILABLE
    if _PG_AVAILABLE is not None:
        return _PG_AVAILABLE
    try:
        with socket.create_connection((host, port), timeout=timeout):
            _PG_AVAILABLE = True
    except (OSError, ConnectionRefusedError):
        _PG_AVAILABLE = False
    return _PG_AVAILABLE


# ---------------------------------------------------------------------------
# Auto-skip hook for @pytest.mark.db
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    """Auto-skip tests marked @pytest.mark.db when PostgreSQL is unreachable."""
    if _pg_is_available():
        return
    skip_db = pytest.mark.skip(reason="PostgreSQL not available on localhost:5432")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip_db)


# ---------------------------------------------------------------------------
# Live DB fixtures (session-scoped, read-only)
# ---------------------------------------------------------------------------

DB_PARAMS = {"host": "localhost", "port": 5432, "user": "cregan1", "database": "gex_options"}


@pytest.fixture(scope="session")
def pg_options_manager():
    """Session-scoped PostgreSQLOptionsManager (read-only)."""
    from gex_db_infrastructure import PostgreSQLOptionsManager

    mgr = PostgreSQLOptionsManager(**DB_PARAMS)
    yield mgr
    mgr.close()


@pytest.fixture(scope="session")
def pg_intraday_gex_manager():
    """Session-scoped IntradayGexManager (read-only)."""
    from gex_db_infrastructure import IntradayGexManager

    mgr = IntradayGexManager(**DB_PARAMS)
    yield mgr
    mgr.close()


@pytest.fixture(scope="session")
def pg_equity_snapshots_manager():
    """Session-scoped EquitySnapshotsManager (read-only)."""
    from gex_db_infrastructure import EquitySnapshotsManager

    mgr = EquitySnapshotsManager(**DB_PARAMS)
    yield mgr
    mgr.close()


@pytest.fixture(scope="session")
def pg_raw_connection():
    """Raw psycopg2 connection for direct SQL queries."""
    import psycopg2

    conn = psycopg2.connect(**DB_PARAMS)
    conn.set_session(readonly=True, autocommit=True)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# Mock fixtures (no PostgreSQL required)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_options_chain():
    """Realistic 10-contract SPY options chain DataFrame."""
    np.random.seed(42)
    strikes = np.arange(590, 610, 2.0)
    n = len(strikes)
    return pd.DataFrame(
        {
            "symbol": "SPY",
            "strike": strikes,
            "expiration": "2026-03-20",
            "option_type": ["call"] * 5 + ["put"] * 5,
            "last_price": np.random.uniform(1.0, 20.0, n),
            "bid": np.random.uniform(0.5, 19.5, n),
            "ask": np.random.uniform(1.5, 20.5, n),
            "volume": np.random.randint(100, 10000, n),
            "open_interest": np.random.randint(1000, 50000, n),
            "implied_volatility": np.random.uniform(0.12, 0.35, n),
            "delta": np.concatenate(
                [np.random.uniform(0.3, 0.8, 5), np.random.uniform(-0.8, -0.3, 5)]
            ),
            "gamma": np.random.uniform(0.005, 0.03, n),
            "theta": np.random.uniform(-0.5, -0.01, n),
            "vega": np.random.uniform(0.05, 0.30, n),
        }
    )


@pytest.fixture
def mock_options_manager(mock_options_chain):
    """MagicMock PostgreSQLOptionsManager with realistic responses."""
    mgr = MagicMock()
    mgr.retrieve_options_chain.return_value = mock_options_chain
    mgr.has_options_data.return_value = True
    mgr.get_database_stats.return_value = {
        "total_options_records": 123_800_000,
        "total_symbols": 62,
        "date_range": ("2020-01-02", "2025-12-31"),
    }
    return mgr


@pytest.fixture
def mock_gex_snapshots():
    """5-snapshot GEX time series for a single symbol."""
    timestamps = pd.date_range("2026-02-14 09:30", periods=5, freq="30min")
    return pd.DataFrame(
        {
            "symbol": "SPY",
            "snapshot_timestamp": timestamps,
            "regime": ["persistent_positive"] * 3 + ["transitional"] * 2,
            "total_gex": [5e9, 4.8e9, 5.2e9, 2.1e9, -0.5e9],
            "zero_gamma_level": [598.5, 598.2, 598.8, 599.1, 599.5],
            "call_gex": [8e9, 7.5e9, 8.5e9, 5e9, 3e9],
            "put_gex": [-3e9, -2.7e9, -3.3e9, -2.9e9, -3.5e9],
        }
    )


@pytest.fixture
def mock_intraday_gex_manager(mock_gex_snapshots):
    """MagicMock IntradayGexManager with realistic responses."""
    mgr = MagicMock()
    mgr.retrieve_gex_snapshots.return_value = mock_gex_snapshots
    mgr.get_latest_gex.return_value = {
        "symbol": "SPY",
        "regime": "persistent_positive",
        "total_gex": 5.2e9,
        "zero_gamma_level": 598.8,
    }
    mgr.get_regime_changes.return_value = [
        {"from": "transitional", "to": "persistent_positive", "date": "2026-02-10"},
        {"from": "persistent_positive", "to": "transitional", "date": "2026-02-14"},
    ]
    mgr.get_snapshot_count.return_value = 21
    return mgr
