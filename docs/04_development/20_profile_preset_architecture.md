# Profile vs Preset Architecture

**Date**: 2025-12-15
**Issues**: #364 (Ranked Voting), #407 (Custom Timeframes)
**Status**: Design Document

---

## Executive Summary

This document defines the separation between **presets** (static, read-only defaults) and **profiles** (user-modified state). This architecture enables:

- Reset-to-defaults functionality
- Audit trail for configuration changes
- Extensibility for watchlists and other user preferences

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         CONFIGURATION LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   config_defaults/                    state/user.db                  │
│   ├─ voters_config.yaml              ├─ voter_profiles              │
│   │  └─ presets: {...}               │  └─ user modifications       │
│   │                                  │                               │
│   ├─ scanner_config.yaml             ├─ watchlist_profiles          │
│   │  └─ default_watchlist: {...}     │  └─ custom watchlists        │
│   │                                  │                               │
│   └─ trading_modes.yaml              └─ voter_ranking_history       │
│      └─ mode configs                    └─ audit trail              │
│                                                                      │
│   STATIC (read-only)                 DYNAMIC (user-modified)        │
│   Reset defaults source              Current active state           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Presets (Static)

**Location**: `config_defaults/*.yaml`
**Characteristics**:

- Read-only at runtime
- Source of truth for "factory defaults"
- Versioned with code (git)
- Never modified by user actions

**Examples**:

```yaml
# voters_config.yaml
presets:
  default:
    description: "Validated MACD+RSI voting (0.856 Sharpe)"
    active_voters: 2
    ranking:
      - {name: MACD, rank: 1, role: active}
      - {name: RSI, rank: 2, role: active}

  macd_primary:
    description: "MACD-focused with RSI confirmation"
    # ...
```

### Profiles (Dynamic)

**Location**: `state/user.db`
**Characteristics**:

- User-modifiable at runtime
- Starts from a preset (base)
- Persisted across sessions
- Full audit trail

**When created**: When user modifies any preset value, a new profile is created.

---

## Database Schema

### Table: voter_profiles (NEW)

```sql
CREATE TABLE voter_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL UNIQUE,
    base_preset TEXT NOT NULL,              -- Original preset this was based on
    ranking_json TEXT NOT NULL,             -- Current voter ranking
    voting_config_json TEXT,                -- Custom voting parameters
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE         -- Currently active profile
);

-- Example row
INSERT INTO voter_profiles VALUES (
    1,
    'my_custom_setup',
    'default',                              -- Based on 'default' preset
    '[{"name":"MACD","rank":1,"role":"active"},{"name":"RSI","rank":2,"role":"review"}]',
    '{"consensus_mode":"majority"}',
    '2025-12-15T10:00:00',
    '2025-12-15T14:30:00',
    TRUE
);
```

### Table: watchlist_profiles (NEW)

```sql
CREATE TABLE watchlist_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL UNIQUE,
    symbols_json TEXT NOT NULL,             -- Array of symbols
    tier_overrides_json TEXT,               -- Custom tier assignments
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE
);

-- Example row
INSERT INTO watchlist_profiles VALUES (
    1,
    'my_tech_focus',
    '["AAPL","MSFT","NVDA","AMD","GOOGL"]',
    '{"NVDA":"positions","AMD":"strategy"}',
    '2025-12-15T10:00:00',
    '2025-12-15T14:30:00',
    TRUE
);
```

### Table: voter_ranking_history (EXISTING)

```sql
-- Already exists, used for audit trail
CREATE TABLE voter_ranking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    ranking_json TEXT NOT NULL,
    preset_name TEXT,                       -- NULL if from profile
    profile_name TEXT,                      -- NULL if from preset (NEW column)
    reason TEXT
);
```

---

## Workflow

### 1. System Startup

```text
1. Load presets from YAML (read-only reference)
2. Check DB for active profile
   - If exists: Use profile settings
   - If not: Apply default preset, no profile created yet
3. Initialize voters/watchlist with active configuration
```

### 2. User Applies Preset

```text
User: /voter preset macd_primary

1. Load preset from YAML
2. Update current runtime state
3. Log to voter_ranking_history with preset_name
4. DO NOT create profile (still using pure preset)
```

### 3. User Modifies Configuration

```text
User: /voter promote RSI

1. Check if active profile exists
   - If no profile: Create new profile based on current preset
2. Apply modification to profile
3. Save to voter_profiles table
4. Log to voter_ranking_history with profile_name
```

### 4. User Resets to Defaults

```text
User: /voter reset

1. Deactivate current profile (is_active = FALSE)
2. Load 'default' preset from YAML
3. Apply preset (no profile active)
4. Log to history with reason "Reset to defaults"
```

---

## API Design

### RankedVoterManager (Updated)

```python
class RankedVoterManager:
    """
    Manages presets (static) and profiles (dynamic) for voter configuration.
    """

    # Preset operations (read-only)
    def get_available_presets(self) -> Dict[str, str]: ...
    def apply_preset(self, preset_name: str) -> bool: ...
    def get_preset_config(self, preset_name: str) -> Dict: ...

    # Profile operations (read-write)
    def get_active_profile(self) -> Optional[str]: ...
    def create_profile(self, name: str, base_preset: str) -> bool: ...
    def save_profile(self) -> bool: ...
    def delete_profile(self, name: str) -> bool: ...
    def list_profiles(self) -> List[str]: ...

    # State operations
    def is_using_preset(self) -> bool: ...     # True if no modifications
    def is_using_profile(self) -> bool: ...    # True if user-modified
    def get_base_preset(self) -> str: ...      # Which preset this is based on

    # Reset
    def reset_to_defaults(self) -> bool: ...   # Deactivate profile, use default preset
```

### CLI Commands (Phase 2)

```text
/voter list                    # Show current ranking
/voter preset <name>           # Apply preset (pure, no profile)
/voter preset list             # List available presets
/voter promote <indicator>     # Creates profile if needed
/voter demote <indicator>      # Creates profile if needed
/voter profile save <name>     # Save current state as named profile
/voter profile load <name>     # Load saved profile
/voter profile list            # List user profiles
/voter reset                   # Reset to default preset
```

---

## Value-Added Features

### 1. Reset to Defaults

Users can always return to known-good configuration:

```text
User: /voter reset
→ Profile deactivated
→ Using preset: default (MACD+RSI validated 0.856 Sharpe)
```

### 2. Audit Trail

Full history of changes with context:

```sql
SELECT timestamp, preset_name, profile_name, reason
FROM voter_ranking_history
ORDER BY timestamp DESC LIMIT 10;

-- Result:
-- 2025-12-15 14:30:00 | NULL    | my_setup | Promoted RSI
-- 2025-12-15 14:00:00 | default | NULL     | Applied preset: default
-- 2025-12-15 10:00:00 | NULL    | NULL     | System initialization
```

### 3. Named Profiles

Save and switch between configurations:

```text
/voter profile save aggressive_macd
/voter profile save conservative_dual
/voter profile list
→ aggressive_macd (based on: macd_primary)
→ conservative_dual (based on: default)
/voter profile load aggressive_macd
```

### 4. Profile-Watchlist Association

Profiles can include watchlist preferences:

```text
Profile: day_trading
  - Voters: MACD only (fast signals)
  - Watchlist: TQQQ, SQQQ, SPY (high-volume)
  - Timeframe preset: scalping (5m/15m/1h)

Profile: swing_trading
  - Voters: MACD + RSI (confirmation)
  - Watchlist: AAPL, MSFT, NVDA (tech focus)
  - Timeframe preset: trend_following (1d/4h/1h)
```

---

## Migration Path

### Phase 1: Current State (Implemented)

- voter_ranking_history table exists
- Presets in voters_config.yaml
- No explicit profile support

### Phase 2: Profile Support (This Issue)

- Add voter_profiles table
- Add watchlist_profiles table
- Update RankedVoterManager API
- Add CLI commands

### Phase 3: Integration

- Link profiles to trading modes
- Auto-suggest profiles based on trading style
- Profile templates from community

---

## Implementation Notes

### Profile Creation Trigger

Profile is created automatically on first modification:

```python
def promote_voter(self, name: str) -> bool:
    # If using pure preset, create profile first
    if self.is_using_preset():
        self._create_profile_from_current()

    # Now safe to modify
    self._do_promotion(name)
    self._save_profile()
```

### Preset Immutability

Presets are never modified at runtime:

```python
def apply_preset(self, preset_name: str) -> bool:
    # Load from YAML (immutable source)
    preset = self._load_preset_from_yaml(preset_name)

    # Deactivate any active profile
    self._deactivate_current_profile()

    # Use preset directly (no profile)
    self._current_ranking = preset.ranking
    self._current_source = ("preset", preset_name)
```

---

## See Also

- [CONFIG_SCHEMA_REVIEW.md](./CONFIG_SCHEMA_REVIEW.md) - YAML configuration details
- [CLI_INTEGRATION_STATUS.md](./CLI_INTEGRATION_STATUS.md) - CLI command implementation
- GitHub Issues: #364, #488
