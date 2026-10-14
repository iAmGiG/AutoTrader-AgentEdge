"""
Settings priority (argument > config > default) and state files that live in the shared
state dir, not wherever the process happens to be started.
"""

from unittest.mock import MagicMock

import pytest

import src.trading.gtt.gtt_manager as gtt_module
import src.trading.positions.position_manager as position_module
import src.trading.risk.simple_risk_manager as risk_module
from src.utils.state_paths import STATE_DIR_ENV, get_state_dir


class _Config:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


@pytest.mark.parametrize(
    "kwargs, config, expected",
    [
        ({"max_position_pct": 9.0}, {"risk.max_position_pct": 20.0}, 9.0),  # argument wins
        ({}, {"risk.max_position_pct": 20.0}, 20.0),  # then config
        ({}, {}, 15.0),  # then the default
    ],
)
def test_risk_settings_priority(monkeypatch, kwargs, config, expected):
    monkeypatch.setattr(risk_module, "ConfigLoader", lambda: _Config(config))

    assert risk_module.SimpleRiskManager(**kwargs).max_position_pct == expected


def _elsewhere(monkeypatch, tmp_path):
    """Run from a directory other than the state dir; a cwd-relative path lands here."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def test_gtt_uses_the_shared_user_db(monkeypatch, tmp_path):
    cwd = _elsewhere(monkeypatch, tmp_path)
    monkeypatch.delenv(STATE_DIR_ENV, raising=False)
    shared_db = tmp_path / "shared" / "user.db"
    shared_db.parent.mkdir()
    monkeypatch.setattr(gtt_module, "get_user_db_path", lambda: str(shared_db))

    manager = gtt_module.GTTManager()

    assert manager._db_path == str(shared_db)
    assert not (cwd / "state").exists()


def test_positions_backup_lives_in_the_state_dir(monkeypatch, tmp_path):
    cwd = _elsewhere(monkeypatch, tmp_path)
    monkeypatch.setattr(position_module, "ConfigLoader", lambda: _Config())

    manager = position_module.PositionManager(MagicMock())

    assert manager.state_file == get_state_dir() / "positions.json"
    assert not (cwd / "state").exists()
