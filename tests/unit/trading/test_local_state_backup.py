"""
Local state saves (#599): atomic writes, and one backup of the file before the first save
that drops tracker entries saved under the old timestamp keys.
"""

import json

import pytest

import src.trading.state.local_state_manager as lsm_module
from src.trading.positions.position_tracker import PositionTracker
from src.trading.state.local_state_manager import LocalStateManager


def _entry(position_id, ticker):
    return {
        "position_id": position_id,
        "ticker": ticker,
        "entry_date": "2025-12-11T10:40:55",
        "entry_price": 657.6,
        "quantity": 14,
        "take_profit_price": None,
        "stop_loss_price": 744.47,
        "status": "ACTIVE",
        "alert_history": [],
    }


def _state(*tracker_keys):
    return {
        "positions": {"SPY": {"entry_price": 657.6, "quantity": 14, "stop_price": 744.47}},
        "last_update": "2026-10-27T13:20:06",
        "discrepancies": [],
        "position_tracker_state": {
            "alert_counter": 0,
            "positions": {key: _entry(key, key.split("_")[0]) for key in tracker_keys},
        },
    }


def _manager(state_file):
    tracker = PositionTracker(take_profit_pct=0.08, stop_loss_pct=0.05)
    return LocalStateManager(str(state_file), position_tracker=tracker), tracker


def _backups(state_dir):
    return sorted((state_dir / "backups").glob("cost_efficient_positions.*.pre_tracker_prune.json"))


def test_the_first_save_backs_up_a_file_with_old_tracker_keys(tmp_path):
    state_file = tmp_path / "cost_efficient_positions.json"
    state_file.write_text(json.dumps(_state("SPY_20251211_104055", "AAPL_20251211_104055")))
    original = state_file.read_bytes()
    manager, tracker = _manager(state_file)

    tracker.sync_position("SPY", 657.6, 14, 744.47)
    tracker.prune(["SPY"])
    manager.save()
    manager.save()

    backups = _backups(tmp_path)
    assert len(backups) == 1 and backups[0].read_bytes() == original
    saved = json.loads(state_file.read_text())
    assert list(saved["position_tracker_state"]["positions"]) == ["SPY"]


def test_no_backup_when_the_tracker_keys_are_current(tmp_path):
    state_file = tmp_path / "cost_efficient_positions.json"
    state_file.write_text(json.dumps(_state("SPY")))
    manager, _ = _manager(state_file)

    manager.save()

    assert _backups(tmp_path) == []


def test_a_failed_backup_saves_nothing_and_the_next_save_retries(tmp_path, monkeypatch):
    state_file = tmp_path / "cost_efficient_positions.json"
    state_file.write_text(json.dumps(_state("SPY_20251211_104055")))
    original = state_file.read_bytes()
    manager, tracker = _manager(state_file)
    tracker.prune([])

    def no_space(*args, **kwargs):
        raise OSError("No space left on device")

    with monkeypatch.context() as patch:
        patch.setattr(lsm_module.shutil, "copy2", no_space)
        manager.save()
    assert state_file.read_bytes() == original

    manager.save()
    assert len(_backups(tmp_path)) == 1
    assert json.loads(state_file.read_text())["position_tracker_state"]["positions"] == {}


def test_a_failed_rename_leaves_the_old_file_whole(tmp_path, monkeypatch):
    state_file = tmp_path / "cost_efficient_positions.json"
    state_file.write_text(json.dumps(_state("SPY")))
    original = state_file.read_bytes()
    manager, _ = _manager(state_file)

    def fail(*args, **kwargs):
        raise OSError("disk full")

    with monkeypatch.context() as patch:
        patch.setattr(lsm_module.os, "replace", fail)
        manager.save()  # logged, not raised

    assert state_file.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == [state_file.name]  # no temp file left


def test_a_write_that_fails_midway_leaves_the_old_file_whole(tmp_path):
    state_file = tmp_path / "cost_efficient_positions.json"
    state_file.write_text(json.dumps(_state("SPY")))
    original = state_file.read_bytes()
    manager, _ = _manager(state_file)
    manager.state["positions"]["SPY"]["bad"] = object()  # json.dump fails partway

    with pytest.raises(TypeError):
        manager.save()

    assert state_file.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == [state_file.name]
