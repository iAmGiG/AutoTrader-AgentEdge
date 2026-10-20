# Position Management Enhancements (Issue #306)

## Overview

This document describes the enhancements made to the position management system to provide better exit alerts and dynamic stop integration for live trading monitoring.

## Enhancements Summary

### 1. Exit Alert System

**Location**: `src/trading/positions/position_tracker.py`

#### New Alert Types

- `APPROACHING_TAKE_PROFIT` - Price within 2% of take profit target
- `APPROACHING_STOP_LOSS` - Price within 2% of stop loss level
- `STOP_ADJUSTED` - Stop loss order has been adjusted
- `PROFIT_TARGET_REACHED` - Take profit level reached
- `LOSS_THRESHOLD_REACHED` - Stop loss level reached

#### Alert Severity Levels

- **INFO** (📊) - Informational alerts
- **WARNING** (⚠️) - Warning alerts (approaching exit levels)
- **CRITICAL** (🚨) - Critical alerts (exit levels reached)

#### Alert Features

1. **Alert History Tracking** - Each position maintains a complete history of alerts
2. **Alert Cooldown** - Prevents alert spam with configurable cooldown period (default: 5 minutes)
3. **Formatted Messages** - Human-readable alert messages with emojis for quick scanning
4. **Alert Summary** - Portfolio-wide alert summaries with counts by severity

#### How Alerts Are Triggered

**Alert Destination:** Console/terminal output, log files, and daily reports only. No email, SMS, or webhooks in this implementation.

**Manual Triggering:**

```bash
# Check alerts from the interactive CLI
python main.py
> check my alerts
```

**Automatic Triggering (Daily Scheduler, Issue #287):**
Alerts run automatically in each routine:

- **9:20 AM ET** - Morning routine checks positions
- **3:50 PM ET** - Evening routine checks positions

Only positions with an entry, a stop and a target price are checked
(`StateReconciler.check_position_alerts`). A position whose take-profit order lapsed exits by its
trailing stop and gets no alerts.

Deployment options:

```bash
# Option A (recommended): crontab (the scheduler decides what is due, in ET, on trading days)
*/5 * * * * cd /path/to/repo && /path/to/python main.py --run-due

# Option B: systemd daemon (runs continuously)
sudo systemctl start autogen-trading-scheduler
```

#### Example Usage (Programmatic)

```python
from src.trading.positions.position_tracker import PositionTracker

# Initialize tracker with custom cooldown
tracker = PositionTracker(
    take_profit_pct=0.08,
    stop_loss_pct=0.05,
    alert_cooldown_seconds=300  # 5 minutes between repeated alerts
)

# Create position
position = tracker.create_position(
    ticker="TQQQ",
    entry_price=50.0,
    quantity=100
)

# Check for exit conditions/alerts
result = tracker.check_exit_conditions(position.position_id, current_price=53.5)

# Get alert summary
summary = tracker.get_alert_summary()
print(f"Total alerts: {summary['counts']['total']}")
print(f"Critical: {summary['counts']['critical']}")

# Get position-specific alerts
alerts = tracker.get_position_alerts(position.position_id)
for alert in alerts:
    print(alert.format_message())
```

#### Alert Output Locations

**1. Console Output (Real-time):**

```text
📊 Checking Position Alerts...
   🔔 2 Alert(s) Generated:
      ⚠️ TQQQ approaching take profit! Current: $53.85, Distance: 1.85%
      📊 SPY stop adjusted: $448.00 → $450.00
```

**2. Log Files (Persistent):**

```text
# state/scheduler.log
2025-01-10 09:30:00 WARNING ⚠️ TQQQ approaching take profit! Current: $53.85, Distance: 1.85%
2025-01-10 09:30:00 INFO 📊 SPY stop adjusted: $448.00 → $450.00
```

**3. Daily Reports (Markdown):**

```markdown
# reports/daily/2025-01-10_morning.md

## Position Alerts
Total Alerts: 2 (🚨 0 Critical, ⚠️ 2 Warning, 📊 0 Info)

⚠️ TQQQ approaching take profit! Current: $53.85, Distance: 1.85%
📊 SPY stop adjusted: $448.00 → $450.00
```

**4. In-Memory (During Execution):**
Each position maintains complete alert history:

```python
position.alert_history = [PositionAlert(...), PositionAlert(...)]
position.last_alert_time = datetime(2025, 1, 10, 9, 30, 0)
```

### 2. Dynamic Stop Integration

**Location**: `src/trading/scheduling/trading_cycle.py`, `src/trading/state/state_reconciler.py`, `src/trading/orders/trailing_stop_manager.py`

#### Enhanced Stop Adjustment Logic

The progressive stop adjustment system now includes detailed logging at every step. Stops only move up; by profit since entry:

1. **Under 2% Profit** → No change
2. **2-4% Profit** → Move stop to breakeven
3. **4-6% Profit** → Lock in 25% of gains
4. **6-10% Profit** → Lock in 50% of gains
5. **10%+ Profit** → Lock in 75% of gains

The level is capped 1% below the current price and starts from the broker's live stop.

#### Logging Enhancements

- **DEBUG Level**: Detailed order IDs, price calculations, adjustment decisions
- **INFO Level**: Stop adjustment recommendations, execution results
- **WARNING Level**: Missing stop orders, failed modifications

#### Example Log Output

```text
INFO: TQQQ: Moving stop to breakeven at 3.2% profit
INFO: TQQQ: Stop adjustment - $47.50 → $50.00 (Move to breakeven (3.2% profit))
INFO: Found 1 stop adjustments needed
INFO: [1/1] Modifying TQQQ stop order...
INFO: ✅ TQQQ: Stop adjusted to $50.00 (locking +$0.00 profit)
INFO: Stop adjustment batch complete: 1/1 successful, 0 errors
```

### 3. Trading Cycle Integration

**Location**: `src/trading/scheduling/trading_cycle.py`, `main.py`

#### New Workflow Steps

The trading cycle now includes alert checking:

1. Fetch broker state and record the day (account, positions, fills)
2. Reconcile local state, and re-place missing or expiring stops
3. **Check position alerts** ← NEW
4. Check GTT triggers
5. Raise stops to their trailing level (evening: only while the market is open)
6. Generate report with alerts

#### Report Format

Reports now include a Position Alerts section:

```markdown
## Position Alerts

Total Alerts: 2 (🚨 0 Critical, ⚠️ 2 Warning, 📊 0 Info)

⚠️ TQQQ approaching take profit! Current: $53.85, Distance: 1.85%
⚠️ SPY approaching stop loss! Current: $448.20, Distance: 1.50%
```

### 4. Main Trading Interface

**Location**: `main.py`

The main trading interface now displays alerts during the position monitoring cycle:

```text
📊 Checking Position Alerts...
   🔔 2 Alert(s) Generated:
      ⚠️ TQQQ approaching take profit! Current: $53.85, Distance: 1.85%
      ⚠️ SPY approaching stop loss! Current: $448.20, Distance: 1.50%
```

## Configuration

### Position Tracker Configuration

```python
tracker = PositionTracker(
    take_profit_pct=0.08,           # 8% take profit
    stop_loss_pct=0.05,             # 5% stop loss
    alert_cooldown_seconds=300      # 5 minute cooldown
)
```

### Stop Adjustment Thresholds

These are the `TrailingStopConfig` defaults (`config_defaults/trading_config.py`, `climb_rate: medium`); a `trailing_stops` section in `trading_config.yaml` overrides them:

- **Minimum profit for adjustment**: 2%
- **Breakeven threshold**: 2-4% profit
- **Lock 25% threshold**: 4-6% profit
- **Lock 50% threshold**: 6-10% profit
- **Lock 75% threshold**: 10%+ profit
- **Cap**: at least 1% below the current price
- **Minimum stop movement**: $0.01

## API Reference

### PositionTracker Class

#### Methods

- `create_position(ticker, entry_price, quantity)` - Create new position
- `check_exit_conditions(position_id, current_price)` - Check for exits/alerts
- `get_all_alerts(since=None)` - Get all alerts (optionally filtered)
- `get_position_alerts(position_id)` - Get alerts for specific position
- `get_alert_summary()` - Get portfolio-wide alert summary
- `get_position_summary(current_prices)` - Get position summary with P&L

### CostEfficientTradeCycle Class

#### New Methods

- `check_position_alerts(broker_state)` - Check all positions for alerts
- Returns `List[PositionAlertSummary]`

#### Enhanced Methods

- `generate_routine_report()` - Now includes alerts parameter
- `morning_routine()` - Includes alert checking
- `evening_routine()` - Includes alert checking

## Testing

There is no dedicated tracked test file for the alert system yet. Run the trading unit tests with:

```bash
python -m pytest tests/unit/trading/ -v
```

Test coverage:

- ✅ Alert creation and formatting
- ✅ Alert cooldown functionality
- ✅ Alert summary and history
- ✅ Position summary with multiple positions

## Alert Execution Flow

### Step-by-Step Process

```text
1. Trigger Event
   ├─> Manual: "check my alerts" in the CLI
   └─> Auto: Daily scheduler at 9:20 AM / 3:50 PM ET (Issue #287)

2. Trading Cycle Execution
   └─> morning_routine() / evening_routine()

3. Broker State Fetch (1 API call)
   └─> Get all positions with current prices

4. Alert Check Loop
   For each position:
   ├─> Calculate distance to take profit (TP)
   ├─> Calculate distance to stop loss (SL)
   ├─> If within 2% of TP:
   │   └─> Check cooldown → Generate APPROACHING_TP alert
   ├─> If within 2% of SL:
   │   └─> Check cooldown → Generate APPROACHING_SL alert
   ├─> If TP reached:
   │   └─> Generate PROFIT_TARGET_REACHED alert (CRITICAL)
   └─> If SL reached:
       └─> Generate LOSS_THRESHOLD_REACHED alert (CRITICAL)

5. Alert Cooldown Check (Anti-Spam)
   ├─> Has 5+ minutes passed since last alert for this position?
   ├─> Yes: Create alert, update last_alert_time
   └─> No: Skip (prevents spam from price fluctuations)

6. Alert Storage & Display
   ├─> Add to position.alert_history[]
   ├─> Log to console (INFO/WARNING/CRITICAL level)
   ├─> Write to state/scheduler.log (scheduler runs)
   └─> Include in daily report markdown

7. Continue Trading Cycle
   └─> Calculate stop adjustments, execute modifications, etc.
```

### Alert Frequency

**Manual:**

- "check my alerts" in the CLI
- On-demand basis

**Daily Scheduler (Issue #287):**

- Twice daily automatically (9:20 AM, 3:50 PM ET)
- Plus manual runs anytime
- Alert history persists across runs

### Alert Cooldown Behavior

**Problem:** Stock price fluctuates near threshold

```text
09:30:00 - Price: $53.85 (1.85% from TP) → ⚠️ Alert sent
09:30:30 - Price: $53.80 (1.95% from TP) → ⏭️ Skipped (cooldown)
09:31:00 - Price: $53.90 (1.75% from TP) → ⏭️ Skipped (cooldown)
09:35:01 - Price: $53.95 (1.25% from TP) → ⚠️ Alert sent (5 min elapsed)
```

**Result:** You get updates every 5 minutes max, not every price tick.

## Benefits for Live Trading

1. **Early Warning System** - Get notified before positions reach exit levels
2. **No Alert Spam** - Cooldown prevents repeated alerts for the same condition
3. **Complete History** - Track all alerts for post-trade analysis
4. **Clear Visibility** - Human-readable messages with severity indicators
5. **Enhanced Logging** - Detailed logs for debugging stop adjustments
6. **Portfolio Overview** - See all alerts across positions at a glance

## Limitations & Future Enhancements

### Current Limitations

**❌ No External Notifications:**

- Alerts are **console/log output only**
- No email, SMS, or push notifications
- Must actively check logs or run system to see alerts
- If daemon crashes, alerts are not sent

**⚠️ Twice-Daily Checks Only (with GTC):**

- Alerts checked at 9:20 AM and 3:50 PM ET only
- Positions could reach exit levels between checks without alert
- Not real-time monitoring (by design for API efficiency)

**⚠️ Manual Monitoring Required:**

- You must view console output or check log files
- No proactive notification mechanism
- Alert history in memory is lost on restart (unless persisted)

### Recommended Workflow

**For Active Monitoring:**

```bash
# Check alerts ad-hoc during the trading day
python main.py      # then: check my alerts

# View recent logs
tail -f state/scheduler.log

# Check daily reports
cat reports/daily/$(TZ=America/New_York date +%Y-%m-%d)_morning.md
```

**For Automated Monitoring (with GTC #287):**

```bash
# Recommended: cron entry (see 02_gtc_scheduler_quickstart.md)
crontab -l | grep "main.py --run-due"

# Monitor logs in real-time (cron and daemon runs both write here)
tail -f state/scheduler.log

# Cron errors
cat state/scheduler-cron.err
```

### Future Enhancements

Potential improvements for future iterations:

1. **Email/SMS Notifications** - Send critical alerts via external channels (Twilio, SendGrid)
2. **Alert Webhooks** - Integrate with external monitoring systems (PagerDuty, Slack)
3. **Custom Alert Rules** - User-defined alert conditions beyond 2% threshold
4. **Alert Analytics** - Statistical analysis of alert patterns
5. **Mobile App Integration** - Push notifications to mobile devices
6. **Real-Time WebSocket Alerts** - Continuous monitoring instead of scheduled checks
7. **Alert Dashboard** - Web UI for viewing alert history and current status

## Changelog

### v1.0.0 (Issue #306)

- ✅ Added comprehensive exit alert system
- ✅ Enhanced position tracking with alert history
- ✅ Integrated alerts into trading cycle
- ✅ Added detailed logging for stop adjustments
- ✅ Updated main.py to display alerts
- ✅ Created test suite for alert functionality
- ✅ Documentation complete

## Related Files

- `src/trading/positions/position_tracker.py` - Core alert system
- `src/trading/scheduling/trading_cycle.py` - Trading cycle integration
- `src/trading/positions/position_manager.py` - Position management
- `main.py` - Main trading interface

## References

- Issue #306: Position Management Enhancements
- Issue #321: Dynamic trailing stop logic
- [Project status](../04_development/02_project_status.md): System development roadmap
