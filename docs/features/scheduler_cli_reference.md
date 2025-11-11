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
- Current enabled/disabled state
- Configuration summary (times, retries, timezone)
- Today's execution count
- Recent execution results

**Example:**
```
Scheduler> status

⏰ Scheduler Status
======================================================================

🟢 Status: ENABLED

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
   Orders placed: 2
   Alerts checked: 5
```

#### `test evening`
Test evening routine immediately

```
Scheduler> test evening

🧪 Testing evening routine...

✅ Evening routine completed
   Orders placed: 0
   Alerts checked: 3
```

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

## Future Enhancements

See pending issues for:
- Background service start/stop from CLI
- Self-terminating background processes
- Real-time execution monitoring
- Custom routine scheduling
- Email/webhook notifications

---

**Related Documentation:**
- [GTC Scheduler Quickstart](02_gtc_scheduler_quickstart.md)
- [GTC Scheduler Technical](03_gtc_scheduler_technical.md)
- [Interactive CLI Test Plan](05_interactive_cli_test_plan.md)
