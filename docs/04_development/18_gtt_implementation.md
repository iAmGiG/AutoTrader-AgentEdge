# GTT (Good-Till-Triggered) Implementation

**Issue:** #340
**Status:** Phase 2 Complete
**Date:** 2025-12-18

---

## Overview

GTT provides persistent price triggers that stay active across sessions (days/weeks), checked automatically by the scheduler.

**Key Characteristics:**

- Checked twice daily (morning 9:20 AM, evening 3:50 PM ET)
- Persist in SQLite across system restarts
- Support repeating or one-time triggers
- OCO (One-Cancels-Other) groups for dual breakout/breakdown

---

## Architecture

```plaintext
src/trading/gtt/
├── __init__.py           # Module exports
├── gtt_manager.py        # SQLite persistence, CRUD operations
├── trigger_evaluator.py  # Condition checking logic
└── action_executor.py    # Execute trigger actions

src/cli/tools/
└── gtt_tools.py          # FunctionTool wrappers for CLI
```

### Integration Points

- **Scheduler:** `trading_cycle.py` calls `check_gtt_triggers()` in morning/evening routines
- **CLI:** Tools registered in `src/cli/tools/__init__.py` under `GTT_TOOLS` category
- **Database:** Uses `state/user.db` (same as alerts_watchlists.py)

---

## Database Schema

```sql
CREATE TABLE gtt_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    condition_type TEXT NOT NULL,  -- price_above, price_below, pct_gain, pct_loss, trailing_stop
    trigger_value REAL NOT NULL,
    action_type TEXT NOT NULL,     -- alert, place_order, cancel_order
    action_config TEXT,            -- JSON: order details, highest_price for trailing
    expiration_date TEXT,          -- ISO timestamp (NULL = no expiration)
    max_triggers INTEGER,          -- NULL = unlimited, 1 = one-time
    trigger_count INTEGER DEFAULT 0,
    last_triggered_at TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    oco_group_id INTEGER,          -- Links OCO pairs
    notes TEXT,
    created_at TEXT NOT NULL
);
```

---

## Condition Types

| Type | Description | Example |
|------|-------------|---------|
| `price_above` | Triggers when price >= value | SPY >= $620 |
| `price_below` | Triggers when price <= value | AAPL <= $180 |
| `pct_gain` | Triggers when gain % reached | +5% from entry |
| `pct_loss` | Triggers when loss % reached | -3% from entry |
| `trailing_stop` | Triggers when drops X% from peak | 5% below highest |
| `time_window` | Active only during specific hours (Phase 2) | 09:30-16:00 ET |
| `volume_above` | Triggers when volume >= threshold (Phase 2) | Volume >= 1M |
| `volume_spike` | Triggers on volume spike vs average (Phase 2) | 2x avg volume |

---

## Action Types

| Type | Description | Phase |
|------|-------------|-------|
| `alert` | Log alert message | Phase 1 (complete) |
| `place_order` | Place market/limit order via AlpacaOrderManager | Phase 2 (complete) |
| `cancel_order` | Cancel existing order via AlpacaOrderManager | Phase 2 (complete) |

---

## CLI Tools

### Create Triggers

```python
create_gtt_trigger(
    symbol="SPY",
    condition="above",      # above, below, gain, loss, trailing
    value=620.0,
    action="alert",         # alert, order
    expiration_days=30,     # Optional
    max_triggers=1,         # Optional (None = unlimited)
    notes="Breakout alert"  # Optional
)
```

### Create OCO Pair

```python
create_gtt_oco_pair(
    symbol="SPY",
    condition_a="above",
    value_a=620.0,
    condition_b="below",
    value_b=580.0,
    expiration_days=30
)
```

### Management

```python
list_gtt_triggers(symbol=None, include_disabled=False)
delete_gtt_trigger(trigger_id=42)
disable_gtt_trigger(trigger_id=42)
enable_gtt_trigger(trigger_id=42)
show_gtt_triggers()
show_gtt_summary()
```

---

## Scheduler Integration

GTT triggers are checked during morning and evening routines:

```python
# In trading_cycle.py
def morning_routine(self):
    broker_state = self.fetch_broker_state()
    discrepancies = self.reconcile_state(broker_state)
    alerts = self.check_position_alerts(broker_state)

    # GTT check (Step 3.5) - Issue #340
    gtt_results = self.check_gtt_triggers(broker_state)

    adjustments = self.calculate_stop_adjustments(broker_state)
    # ... rest of routine
```

---

## Usage Examples

### Simple Price Alert

```text
User> alert if SPY hits $620 in the next 30 days

→ create_gtt_trigger(symbol="SPY", condition="above", value=620, expiration_days=30)

Result:
  GTT Trigger Created (ID: 42)
  Symbol: SPY
  Condition: PRICE_ABOVE $620.00
  Expiration: 2026-01-17 (30 days)
```

### OCO Breakout/Breakdown

```text
User> alert if SPY breaks above $620 or below $580

→ create_gtt_oco_pair(symbol="SPY", condition_a="above", value_a=620,
                       condition_b="below", value_b=580)

Result:
  OCO Trigger Group Created (Group ID: 10)
  Trigger A: SPY PRICE_ABOVE $620.00
  Trigger B: SPY PRICE_BELOW $580.00
  Behavior: When one fires, both disabled
```

### Trailing Stop (Phase 3)

```text
User> set trailing stop 5% on SPY

→ create_gtt_trigger(symbol="SPY", condition="trailing", value=0.05)

Result:
  GTT Trailing Stop Created (ID: 46)
  Condition: TRAILING_STOP (5% from peak)
  Current highest: $615.00
  Stop at: $584.25
```

---

## Differences from User Alerts (#480)

| Feature | User Alerts | GTT Triggers |
|---------|-------------|--------------|
| Persistence | One-time | Repeating OR one-time |
| Actions | Alert only | Alert, orders, cancel |
| Expiration | None | Configurable |
| OCO | Not supported | Supported |
| Trailing | Not supported | Supported |

---

## Phase Roadmap

### Phase 1 (Complete)

- [x] Database schema
- [x] CRUD operations
- [x] Condition evaluation
- [x] Alert actions
- [x] OCO groups
- [x] Scheduler integration
- [x] CLI tools

### Phase 2 (Complete)

- [x] Order placement actions (AlpacaOrderManager integration)
- [x] Cancel order actions (AlpacaOrderManager integration)
- [x] Time-of-day conditions (TIME_WINDOW)
- [x] Volume-based conditions (VOLUME_ABOVE, VOLUME_SPIKE)

### Phase 3 (Planned)

- [ ] Full TrailingStopManager integration
- [ ] Multi-day trailing stop persistence
- [ ] Position-linked triggers

---

## Related Issues

- **#340** - GTT Implementation (this feature)
- **#330** - Options Analysis (GTT can monitor Greeks)
- **#480** - User Alerts (one-time triggers)
- **#321** - Trailing Stops (existing implementation)

---

## Code References

- Manager: [gtt_manager.py](../../src/trading/gtt/gtt_manager.py)
- Evaluator: [trigger_evaluator.py](../../src/trading/gtt/trigger_evaluator.py)
- Executor: [action_executor.py](../../src/trading/gtt/action_executor.py)
- CLI Tools: [gtt_tools.py](../../src/cli/tools/gtt_tools.py)
- Scheduler: [trading_cycle.py](../../src/trading/scheduling/trading_cycle.py)
