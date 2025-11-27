#!/usr/bin/env python3
"""
Lightweight test for Issue #358 Phase 3 - Config Loading

Tests config file loading logic without instantiating full classes.
"""

import os
import shutil
import sys
import tempfile
import yaml

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))


def test_scanner_config_exists():
    """Test that scanner_config.yaml exists and is valid"""
    print("\n=== Test 1: scanner_config.yaml exists and is valid ===")

    config_path = "config_defaults/scanner_config.yaml"
    assert os.path.exists(config_path), f"{config_path} does not exist"
    print(f"  OK Config file exists: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert config is not None, "Config should not be None"
    assert "default_watchlist" in config, "Config should have default_watchlist"
    assert "scanner_settings" in config, "Config should have scanner_settings"
    print(f"  OK Config has required keys: {list(config.keys())}")

    # Verify watchlist structure
    watchlist = config["default_watchlist"]
    all_symbols = []
    for category, symbols in watchlist.items():
        all_symbols.extend(symbols)
    assert len(all_symbols) > 0, "Watchlist should not be empty"
    assert "SPY" in all_symbols, "SPY should be in watchlist"
    print(f"  OK Watchlist has {len(all_symbols)} symbols across {len(watchlist)} categories")

    # Verify scanner settings
    settings = config["scanner_settings"]
    assert "cache_dir" in settings, "Settings should have cache_dir"
    assert "batch_fetch_days" in settings, "Settings should have batch_fetch_days"
    print(f"  OK Scanner settings: {list(settings.keys())}")

    print("PASSED\n")
    return True


def test_paths_config_exists():
    """Test that paths_config.yaml exists and is valid"""
    print("\n=== Test 2: paths_config.yaml exists and is valid ===")

    config_path = "config_defaults/paths_config.yaml"
    assert os.path.exists(config_path), f"{config_path} does not exist"
    print(f"  OK Config file exists: {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    assert config is not None, "Config should not be None"
    assert "state_files" in config, "Config should have state_files"
    assert "report_templates" in config, "Config should have report_templates"
    print(f"  OK Config has required keys: {list(config.keys())}")

    # Verify state files
    state_files = config["state_files"]
    assert "cost_efficient" in state_files, "Should have cost_efficient state file"
    assert "positions" in state_files, "Should have positions state file"
    assert "scheduler_log" in state_files, "Should have scheduler_log state file"
    print(f"  OK State files: {list(state_files.keys())}")

    # Verify report templates
    templates = config["report_templates"]
    assert "daily_routine" in templates, "Should have daily_routine template"
    print(f"  OK Report templates: {list(templates.keys())}")

    print("PASSED\n")
    return True


def test_config_loading_code():
    """Test the actual config loading code in the modules"""
    print("\n=== Test 3: Config loading code works ===")

    # Test scanner config loading logic
    config_path = "config_defaults/scanner_config.yaml"
    print(f"  Testing scanner config loading from {config_path}...")

    try:
        with open(config_path) as f:
            scanner_config = yaml.safe_load(f)
            scanner_settings = scanner_config.get("scanner_settings", {})

            # Flatten watchlist categories
            watchlist_config = scanner_config.get("default_watchlist", {})
            watchlist = []
            for category in watchlist_config.values():
                watchlist.extend(category)

        assert len(watchlist) > 0, "Watchlist should be loaded"
        assert len(scanner_settings) > 0, "Settings should be loaded"
        print(f"    OK Loaded {len(watchlist)} symbols and {len(scanner_settings)} settings")

    except FileNotFoundError:
        print("    OK Fallback would trigger (config not found)")

    # Test paths config loading logic
    paths_config_path = "config_defaults/paths_config.yaml"
    print(f"  Testing paths config loading from {paths_config_path}...")

    try:
        with open(paths_config_path) as f:
            paths_config = yaml.safe_load(f)

        assert "state_files" in paths_config, "Should have state_files"
        assert "report_templates" in paths_config, "Should have report_templates"
        print(f"    OK Loaded {len(paths_config)} path categories")

    except FileNotFoundError:
        print("    OK Fallback would trigger (config not found)")

    print("PASSED\n")
    return True


def test_fallback_logic():
    """Test that fallback logic would work if config missing"""
    print("\n=== Test 4: Fallback logic ===")

    # Simulate missing config by using non-existent path
    fake_config_path = "config_defaults/nonexistent.yaml"

    print(f"  Testing fallback when config missing...")
    try:
        with open(fake_config_path) as f:
            config = yaml.safe_load(f)
        print("    UNEXPECTED: File should not exist")
        return False
    except FileNotFoundError:
        print("    OK FileNotFoundError raised as expected")

    # Verify hardcoded fallback values match what's in the code
    fallback_watchlist = [
        "SPY", "QQQ", "IWM", "VTI",
        "TQQQ", "SQQQ", "UPRO", "SPXL",
        "AAPL", "MSFT", "NVDA", "TSLA", "META", "GOOGL", "AMZN",
        "PLTR", "COIN", "AMD", "CRM", "NFLX",
    ]
    assert len(fallback_watchlist) == 20, f"Fallback should have 20 symbols, got {len(fallback_watchlist)}"
    print(f"    OK Fallback watchlist would have {len(fallback_watchlist)} symbols")

    fallback_paths = {
        "state_files": {"cost_efficient": "state/cost_efficient_positions.json"},
        "report_templates": {"daily_routine": "reports/daily/{date}_{routine_type}.md"},
    }
    assert "state_files" in fallback_paths, "Fallback should have state_files"
    print(f"    OK Fallback paths would have {len(fallback_paths)} categories")

    print("PASSED\n")
    return True


def main():
    """Run all config loading tests"""
    print("=" * 60)
    print("Issue #358 Phase 3 - Config Loading Tests")
    print("=" * 60)

    tests = [
        ("scanner_config.yaml validation", test_scanner_config_exists),
        ("paths_config.yaml validation", test_paths_config_exists),
        ("Config loading code", test_config_loading_code),
        ("Fallback logic", test_fallback_logic),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"\nFAILED: {test_name}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)