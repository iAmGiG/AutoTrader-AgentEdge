"""ConfigLoader: dotted keys read nested sections, and a missing default file isn't fatal."""

import json

import pytest

from src.utils.config_loader import ConfigLoader


def _loader(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    return ConfigLoader(str(path))


def test_dotted_key_reads_nested_section(tmp_path):
    loader = _loader(tmp_path, {"risk": {"max_position_pct": 12.0}})

    assert loader.get("risk.max_position_pct", 15.0) == 12.0


def test_missing_nested_key_returns_default(tmp_path):
    loader = _loader(tmp_path, {"risk": {"max_position_pct": 12.0}, "flat": 1})

    assert loader.get("risk.max_positions", 10) == 10
    assert loader.get("flat.child", "default") == "default"
    assert loader.get("absent", "default") == "default"


def test_exact_top_level_key_wins(tmp_path):
    loader = _loader(tmp_path, {"a.b": 1, "a": {"b": 2}})

    assert loader.get("a.b") == 1


def test_missing_default_file_uses_defaults(tmp_path):
    loader = ConfigLoader.__new__(ConfigLoader)  # as if config/config.json didn't exist
    loader._default_path = True
    loader.config_path = str(tmp_path / "config.json")

    assert loader.load_config() == {}


def test_missing_explicit_file_still_raises(tmp_path):
    with pytest.raises(Exception, match="Error loading config file"):
        ConfigLoader(str(tmp_path / "nope.json"))


def test_null_value_returns_default(tmp_path):
    loader = _loader(tmp_path, {"risk": {"max_position_pct": None}, "MODEL": None})

    assert loader.get("risk.max_position_pct", 15.0) == 15.0
    assert loader.get("MODEL", "gpt-4o-mini") == "gpt-4o-mini"
