# Scheduler CLI Reference

## Overview

The Scheduler CLI provides a dedicated interactive interface for managing the daily trading scheduler. It's accessible via the `/schedule` command from the main trading CLI, or can be run standalone.

## Access Methods

### From Main Trading CLI
```bash
python main.py
> /schedule
```

### Standalone Mode
```bash
python -m src.cli.scheduler_cli
```

## Commands

### Status & Monitoring

#### `status`
Show detailed scheduler status including:
- **Config status** (enabled/disabled in config file)
- **Service status** (daemon actually running or not)
- Configuration summary (times, retries, timezone)
- Today's execution count
- Recent execution results

**IMPORTANT:** "Config: ENABLED" does NOT mean the scheduler is running automatically!
You must start the daemon process for automatic execution.

**Example (config enabled, daemon NOT running):**
```
Scheduler> status

⏰ Scheduler Status
======================================================================

🟢 Config: ENABLED
❌ Service: NOT RUNNING (no automatic execution)

💡 Config is enabled but daemon is not running.
   To start automatic execution:
   1. Exit this CLI
   2. Run: python main.py --daemon
   3. Scheduler will run automatically at scheduled times

   Or use 'test morning/evening' to run manually now

⚙️  Configuration:
   Morning: 09:20:00 ET
   Evening: 15:50:00 ET
   Timezone: America/New_York
   Max Retries: 3
   Dry Run: False

📋 No executions today
   (Daemon not running - no automatic executions)
```

**Example (config enabled, daemon RUNNING):**
```
Scheduler> status

⏰ Scheduler Status
======================================================================

🟢 Config: ENABLED
✅ Service: RUNNING (automatic execution active)

⚙️  Configuration:
   Morning: 09:20:00 ET
   Evening: 15:50:00 ET
   Timezone: America/New_York
   Max Retries: 3
   Dry Run: False

📋 Today's Executions: 2
   ✅ morning_routine - completed
   ✅ evening_routine - completed
```

#### `history`
View execution history (last 20 runs, 7 days)

**Example:**
```
Scheduler> history

📜 Execution History
======================================================================

Showing last 20 executions (7 days):

✅ morning_routine        completed     2025-11-11 09:20
✅ evening_routine        completed     2025-11-11 15:50
✅ morning_routine        completed     2025-11-10 09:20
❌ evening_routine        failed        2025-11-10 15:50
   ⚠️  Connection timeout to Alpaca API...
```

#### `next`
Calculate and show next scheduled run with countdown

**Example:**
```
Scheduler> next

🔮 Next Scheduled Run
======================================================================

⏰ Evening Routine
   Time: 03:50 PM ET
   Countdown: 2h 15m
   Date: 2025-11-11
```

### Configuration Management

#### `config`
Display current scheduler configuration file contents

**Example:**
```
Scheduler> config

⚙️  Scheduler Configuration
======================================================================

Config file: config_defaults/scheduler_config.yaml

enabled: true
market_timezone: "America/New_York"
morning_routine_time: "09:20:00"
evening_routine_time: "15:50:00"
max_retries: 3
...
```

#### `edit`
Interactive configuration editor

**Features:**
- Edit all scheduler settings interactively
- Input validation (time format, ranges)
- Save and reload without restart
- Cancel without changes

**Example Session:**
```
Scheduler> edit

📝 Scheduler Configuration Editor
======================================================================

Current settings:
  1. Enabled: True
  2. Morning routine: 09:20:00
  3. Evening routine: 15:50:00
  4. Max retries: 3
  5. Dry run mode: False
  0. Save and exit
  q. Cancel

Edit setting (1-5, 0 to save, q to cancel): 2
Morning routine time (HH:MM:SS): 09:15:00

Edit setting (1-5, 0 to save, q to cancel): 0
✅ Configuration saved!
🔄 Reloading scheduler...
✅ Scheduler reloaded
```

### Control Commands

#### `enable`
Enable scheduler (sets `enabled: true` in config)

```
Scheduler> enable
✅ Scheduler enabled
```

#### `disable`
Disable scheduler (sets `enabled: false` in config)

```
Scheduler> disable
❌ Scheduler disabled
```

### Testing

#### `test morning`
Test morning routine without waiting for scheduled time

**Example:**
```
Scheduler> test morning

🧪 Testing morning routine...

✅ Morning routine completed

Report preview:
----------------------------------------------------------------------
# Morning Routine Report - 2025-11-11 09:20

## Broker State
- Positions: 2
- Open Orders: 4
- Buying Power: $50,000.00

## Alerts
⚠️ SPY approaching take profit (2.1% away)
✅ TQQQ position healthy

## Actions Taken
- Adjusted 1 stop loss order
...
----------------------------------------------------------------------

Full report saved to: reports/daily/
```

#### `test evening`
Test evening routine immediately

```
Scheduler> test evening

🧪 Testing evening routine...

✅ Evening routine completed

Report preview:
----------------------------------------------------------------------
# Evening Routine Report - 2025-11-11 15:50

## End of Day Summary
- P/L Today: +$125.50 (+0.25%)
- Positions: 2 open, 1 closed
- Orders: 3 pending overnight
...
----------------------------------------------------------------------

Full report saved to: reports/daily/
```

### Report Details

Reports are saved to `reports/daily/` with human-readable filenames:
- First run: `2025-11-11_morning.md`
- Multiple runs: `2025-11-11_morning_2.md`, `2025-11-11_morning_3.md`

**Report Contents**:

1. **Account Summary**
   - Portfolio value, available cash, buying power

2. **Active Positions Table**
   ```
   | Symbol | Entry | Current | Stop | Target | P&L | Action |
   |--------|-------|---------|------|--------|-----|--------|
   | META   | $628  | $625    | $597 | $678   | -$24 | No change |
   | SPY    | $658  | $683    | $625 | $710   | +$350| No change |
   ```
   - **Stop/Target prices** synced from Alpaca GTC orders (not $0.00)
   - **P&L** calculated from current price vs entry
   - **Action** shows if stops were adjusted

3. **Discrepancies** (if any)
   - Positions at broker but not in local state
   - Quantity mismatches (auto-fixed)
   - Ghost positions (removed)

4. **Stop Adjustments** (morning only)
   - Which stops were moved higher
   - New stop prices and modification results

5. **Alerts** (both routines)
   - Positions approaching stop loss
   - Positions approaching take profit
   - Unusual P&L movements

**Note**: Stop and target prices are extracted from your actual GTC orders on Alpaca, ensuring reports always show current exit levels.

### Other Commands

#### `help`
Show command list (same as welcome message)

#### `exit` / `quit` / `q`
Exit scheduler CLI and return to main CLI

## Configuration Fields

Editable via `edit` command:

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `enabled` | boolean | Enable/disable scheduler | `true` |
| `morning_routine_time` | time | Morning execution time (ET) | `09:20:00` |
| `evening_routine_time` | time | Evening execution time (ET) | `15:50:00` |
| `max_retries` | integer (1-10) | Retry attempts on failure | `3` |
| `dry_run` | boolean | Test mode (no real orders) | `false` |

**Read-only fields** (edit config file directly):
- `market_timezone`: Always `America/New_York`
- `retry_delay_seconds`: Initial retry delay (exponential backoff)
- `timeout_seconds`: Max seconds per routine
- `enable_notifications`: Future feature
- `monitoring`: Alert thresholds
- `api_limits`: Rate limiting config

## Use Cases

### Quick Status Check
```bash
python main.py
> /schedule
Scheduler> status
Scheduler> next
Scheduler> exit
```

### Change Execution Times
```bash
Scheduler> edit
# Change morning time from 09:20 to 09:15
# Save and exit
```

### Troubleshoot Failed Execution
```bash
Scheduler> history
# Check error messages
Scheduler> test morning
# Test routine to reproduce issue
```

### Enable/Disable Quickly
```bash
# Disable for maintenance
Scheduler> disable

# Re-enable after maintenance
Scheduler> enable
```

## Best Practices

1. **Always test after editing config**
   ```
   Scheduler> edit
   # Make changes
   Scheduler> test morning
   Scheduler> test evening
   ```

2. **Check history before troubleshooting**
   ```
   Scheduler> history
   # Look for patterns in failures
   ```

3. **Use dry run mode for testing**
   ```
   Scheduler> edit
   # Set dry_run: true
   Scheduler> test morning
   # Verify logic without real orders
   # Set dry_run: false when ready
   ```

4. **Monitor next run before leaving**
   ```
   Scheduler> next
   # Confirm expected time before exiting
   ```

## Integration with Main CLI

The scheduler CLI is fully integrated:

- Shares same `DailyScheduler` instance
- Changes take effect immediately
- No restart needed for config changes
- Seamlessly return to main CLI with `exit`

**Workflow:**
```
Main CLI> /schedule
# Enter scheduler mode
Scheduler> edit
# Make changes
Scheduler> exit
# Return to main CLI
Main CLI> show portfolio
# Continue trading
```

## Limitations

- Cannot start/stop daemon from CLI (use `python main.py --daemon`)
- Background service management requires system integration
- Execution history limited to 7 days (configurable in future)

## Troubleshooting

### Config Editor Error: "yaml referenced before assignment"

**Problem**: `UnboundLocalError: local variable 'yaml' referenced before assignment` when running `edit` command.

**Fix**: Updated in recent version. If you still see this error, ensure you're on the latest code (post-2025-11-11).

**Root Cause**: Redundant `import yaml` statement inside function conflicted with module-level import.

### Reports Show $0.00 for Stop/Target Prices

**Problem**: Morning/evening reports show `$0.00` in Stop column despite take-profit orders existing on Alpaca.

**Example Report**:
```
| Symbol | Entry | Current | Stop | Target | P&L | Action |
| META | $628.07 | $627.00 | $0.00 | $634.19 | $-9 | No change |
| SPY | $657.60 | $683.00 | $0.00 | $712.80 | +$356 | No change |
```

**Root Cause** (2025-11-11): Alpaca's API does NOT return bracket order legs with status "held" (stop-loss orders).

According to [Alpaca forum discussion](https://forum.alpaca.markets/t/half-of-bracket-order-held/2727/5):
> "When a bracket order is submitted, once the entry order is filled, two exit orders are submitted. **Only one of those two orders will be active at a time**. The other will have a status of 'held'."

**The Problem**:
- Alpaca implements OCO (One-Cancels-Other) with one active exit order and one "held" order
- `get_orders()` API (even with `nested=True`) **does not return orders with status="held"**
- Stop-loss orders exist on Alpaca but are invisible to the API
- Attempts to fetch via `get_order_by_id()` also failed - leg IDs return empty

**Pragmatic Solution Implemented** (2025-11-11):

Since Alpaca hides stop orders from the API, the system uses a **"carbon copy" approach**:

1. **Priority 1: Use saved stop** from local state (the actual value sent when placing order)
   ```python
   # Try to use saved stop from local state first
   if symbol in self.local_state.get("positions", {}):
       saved_stop = self.local_state["positions"][symbol].get("stop_price")
   ```

2. **Priority 2: Calculate from entry** if no saved value exists
   ```python
   # Last resort: calculate from entry price × (1 - stop_loss_pct)
   calculated_stop = round(entry_price * 0.95, 2)
   ```

3. **Extract take-profit** prices from API (visible as active LIMIT orders)

4. **Display warning** in reports:
   ```markdown
   ⚠️ **Note**: Stop prices from local state (Alpaca hides bracket order stop-loss legs from API).
   Verify stop orders exist on Alpaca dashboard. See Issue #355 for details.
   ```

**Manual Sync Required**: For AUTO_DISCOVERED positions (not placed by this system), manually update `state/cost_efficient_positions.json` with actual stop prices from Alpaca dashboard.

**Report Example**:
```
| Symbol | Entry | Current | Stop | Target | P&L | Action |
| META | $628.07 | $627.00 | $609.00 | $634.19 | $-9 | No change |
| SPY | $657.60 | $683.00 | $627.00 | $712.80 | +$356 | No change |

⚠️ Note: Stop prices from local state (Alpaca hides bracket order stop-loss legs).
```

**User Responsibility**:
1. Verify stop orders exist on Alpaca web dashboard
2. For AUTO_DISCOVERED positions, manually update stop prices in `state/cost_efficient_positions.json`
3. For new orders placed by this system, stop/target will be saved automatically (when Order Manager integration complete)

**Future Enhancement**: Issue #353 proposes automatically saving stop/target when placing orders via Order Manager integration (requires SQLite #336 for proper persistence).

### Report Filenames with Timestamps

**Old Format** (before 2025-11-11): `20251111_1339_morning.md` (hard to read)

**New Format**: `2025-11-11_morning.md` (human-readable)
- Uses ISO date format with dashes
- Multiple runs same day: `morning_2.md`, `morning_3.md`
- Applies to morning, evening, and recovery reports

### Daemon Not Running Despite "Config: ENABLED"

**Problem**: `status` shows `Config: ENABLED` but scheduler not executing automatically.

**Solution**: "Config: ENABLED" means the config file says `enabled: true`, but you must still start the daemon process:
```bash
# Exit scheduler CLI
Scheduler> exit

# Start daemon in background
python main.py --daemon
```

The `status` command now shows both:
- **Config status** (what's in the YAML file)
- **Service status** (whether daemon is actually running)

## Future Enhancements

See pending issues for:
- Background service start/stop from CLI (#350)
- Self-terminating background processes
- Real-time execution monitoring
- Custom routine scheduling
- Email/webhook notifications

---

**Related Documentation:**
- [GTC Scheduler Quickstart](02_gtc_scheduler_quickstart.md)
- [GTC Scheduler Technical](03_gtc_scheduler_technical.md)
- [Interactive CLI Test Plan](05_interactive_cli_test_plan.md)
