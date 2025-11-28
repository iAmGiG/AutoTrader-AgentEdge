# Configuration Migration Notes

## Overview

Moving hardcoded configuration data to YAML files in `config_defaults/` for better maintainability.

## Current State

### ✅ Already in YAML Config

- `cli_messages.yaml` - All CLI display messages
- `trading_config.yaml` - Trading parameters (MACD, RSI, risk levels)
- `trading_modes.yaml` - Trading mode configurations (conservative/moderate/aggressive)
- `agent_prompts.yaml` - LLM agent system prompts
- `market_hours.yaml` - Market hours configuration
- `scheduler_config.yaml` - Task scheduling settings
- `scanner_config.yaml` - Market scanner settings
- `paths_config.yaml` - File paths configuration

### ✅ Fully Migrated

- `help_commands.yaml` - **COMPLETE** - All 33 CLI help commands
  - Fully migrated from hardcoded Python dict (687 lines removed)
  - Help system now loads from YAML with proper error handling
  - File reduced from ~900 lines to 288 lines (68% reduction)

## Pending Migrations

### Medium Priority

1. **Ticker Watchlists** (if any hardcoded)
   - Check for hardcoded ticker lists
   - Move to `config_defaults/watchlists.yaml`

2. **Error Messages** (if scattered)
   - Audit for hardcoded error messages outside `cli_messages.yaml`
   - Consolidate into YAML

3. **Validation Rules**
   - Trading validation rules (min/max quantities, etc.)
   - Consider `validation_rules.yaml`

### Low Priority

1. **Color Schemes** (if any)
   - Terminal color schemes
   - Move to `ui_config.yaml`

2. **Keyboard Shortcuts** (if any)
   - CLI keyboard mappings
   - Move to `keybindings.yaml`

## Migration Process

### For Help Commands

```python
# BEFORE (in help_system.py)
def _build_help_data(self):
    return {
        "morning-routine": {
            "category": "Workflow",
            "description": "...",
            ...
        }
    }

# AFTER
import yaml

def _build_help_data(self):
    config_path = "config_defaults/help_commands.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)
```

### Benefits of YAML Config

1. **Easier Editing**: Non-programmers can update help text
2. **Version Control**: Cleaner diffs when help text changes
3. **Validation**: Can add schema validation (e.g., pydantic models)
4. **Multilingual**: Easier to support multiple languages later
5. **Hot Reload**: Can reload config without restarting (future feature)

## Code Quality Improvements

### Linter Fixes Applied

- ✅ **help_system.py:804** - Fixed `dict.keys()` iteration (use `.items()` instead)
  - Before: `for cmd in self.commands.keys():`
  - After: `for cmd, cmd_data in self.commands.items():`

### Pre-commit Hook Fixes

- ✅ **Bandit security scanner** - Fixed configuration in `.pre-commit-config.yaml`
  - Changed from `-r src/` to `--recursive` with proper file filters
  - Now passes security scans without errors

## Next Steps

1. **✅ Help System Full Migration - COMPLETED**
   - ✅ Extracted all 33 commands from `help_system.py` using automated script
   - ✅ Generated `help_commands.yaml` via AST parsing migration tool
   - ✅ Updated `HelpSystem._load_help_data()` to load from YAML
   - ✅ Removed 687-line fallback method (enforces YAML-first approach)
   - ✅ File size reduced by 68% (900 → 288 lines)

2. **Config Loader Utility**
   - Create `config_defaults/config_loader.py` if not exists
   - Centralize YAML loading with caching
   - Add schema validation

3. **Documentation**
   - Update developer docs with config file locations
   - Add examples for adding new commands/settings

## Files Modified

- `src/cli/help_system.py` - ✅ **COMPLETE**
  - Linter fixes applied (dict iteration, line length)
  - Migrated to YAML loading with proper error handling
  - Removed 687-line `_build_help_data_fallback()` method
  - Reduced from ~900 lines to 288 lines (68% reduction)
- `config_defaults/help_commands.yaml` - ✅ **COMPLETE** - All 33 commands migrated
- `scripts/migrate_help_to_yaml.py` - **NEW** - Automated migration tool using AST parsing
- `.pre-commit-config.yaml` - Fixed bandit hook
- This file - Migration tracking document
