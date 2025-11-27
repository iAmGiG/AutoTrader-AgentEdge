# Position Management Enhancements (Issue #306)

## Overview

This document describes the enhancements made to the position management system to provide better exit alerts and dynamic stop integration for live trading monitoring.

## Enhancements Summary

### 1. Exit Alert System

**Location**: `src/trading_tools/position_tracker.py`

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

**Manual Triggering (Current Branch Only):**

```bash
# Run position check manually - alerts checked once
python main.py paper-trade SYMBOL
```

**Automatic Triggering (With GTC Daily Execution Branch #287):**
When merged with Issue #287, alerts run automatically:

- **9:20 AM ET** - Morning routine checks all positions
- **3:50 PM ET** - Evening routine checks all positions

Deployment options:

```bash
# Option A: systemd daemon (runs continuously)
sudo systemctl start autogen-trading-scheduler

# Option B: crontab (scheduled runs)
20 9 * * 1-5 /path/to/python src/trading/daily_scheduler.py --mode once --task morning_routine
50 15 * * 1-5 /path/to/python src/trading/daily_scheduler.py --mode once --task evening_routine
```

#### Example Usage (Programmatic)

```python
from src.trading_tools.position_tracker import PositionTracker

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

```
📊 Checking Position Alerts...
   🔔 2 Alert(s) Generated:
      ⚠️ TQQQ approaching take profit! Current: $53.85, Distance: 1.85%
      📊 SPY stop adjusted: $448.00 → $450.00
```

**2. Log Files (Persistent):**

```
# logs/trading.log
2025-01-10 09:30:00 WARNING ⚠️ TQQQ approaching take profit! Current: $53.85, Distance: 1.85%
2025-01-10 09:30:00 INFO 📊 SPY stop adjusted: $448.00 → $450.00
```

**3. Daily Reports (Markdown):**

```markdown
# reports/morning_routine_2025-01-10.md

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

**Location**: `src/trading/trading_cycle.py`

#### Enhanced Stop Adjustment Logic

The progressive stop adjustment system now includes detailed logging at every step:

1. **2-4% Profit** → Move stop to breakeven
2. **4-6% Profit** → Lock in 25% of gains
3. **6%+ Profit** → Trail at 50% of gains

#### Logging Enhancements

- **DEBUG Level**: Detailed order IDs, price calculations, adjustment decisions
- **INFO Level**: Stop adjustment recommendations, execution results
- **WARNING Level**: Missing stop orders, failed modifications

#### Example Log Output

```
INFO: TQQQ: Stop adjustment recommended - Move to breakeven (3.2% profit)
DEBUG: TQQQ: Found stop order ID abc123
INFO: TQQQ: Creating stop adjustment - $47.50 → $50.00 (+$2.50, +5.3%)
INFO: [1/1] Modifying TQQQ stop order...
INFO: ✅ TQQQ: Stop adjusted to $50.00 (locking +$2.50 profit)
INFO: Stop adjustment batch complete: 1/1 successful, 0 errors
```

### 3. Trading Cycle Integration

**Location**: `src/trading/trading_cycle.py`, `main.py`

#### New Workflow Steps

The trading cycle now includes alert checking:

1. Fetch broker state
2. Reconcile local state
3. **Check position alerts** ← NEW
4. Calculate stop adjustments
5. Execute stop modifications
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

```
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

These are hardcoded in the progressive stop logic:

- **Minimum profit for adjustment**: 2%
- **Breakeven threshold**: 2-4% profit
- **Lock 25% threshold**: 4-6% profit
- **Trail 50% threshold**: 6%+ profit
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

Test file location: `tests/test_position_alerts.py`

Run tests:

```bash
python tests/test_position_alerts.py
```

Test coverage:

- ✅ Alert creation and formatting
- ✅ Alert cooldown functionality
- ✅ Alert summary and history
- ✅ Position summary with multiple positions

## Alert Execution Flow

### Step-by-Step Process

```
1. Trigger Event
   ├─> Manual: python main.py paper-trade SYMBOL
   └─> Auto: Daily scheduler at 9:20 AM / 3:50 PM ET (with Issue #287)

2. Trading Cycle Execution
   ├─> run_paper_trading_check() OR
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
   ├─> Write to logs/trading.log
   └─> Include in daily report markdown

7. Continue Trading Cycle
   └─> Calculate stop adjustments, execute modifications, etc.
```

### Alert Frequency

**Without GTC Branch:**

- Only when manually running `python main.py paper-trade`
- On-demand basis

**With GTC Branch (Issue #287 merged):**

- Twice daily automatically (9:20 AM, 3:50 PM ET)
- Plus manual runs anytime
- Alert history persists across runs

### Alert Cooldown Behavior

**Problem:** Stock price fluctuates near threshold

```
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
# Check positions ad-hoc during trading day
python main.py paper-trade SYMBOL

# View recent logs
tail -f logs/trading.log

# Check daily reports
cat reports/morning_routine_$(date +%Y-%m-%d).md
```

**For Automated Monitoring (with GTC #287):**

```bash
# Start daemon
sudo systemctl start autogen-trading-scheduler

# Monitor logs in real-time
sudo journalctl -u autogen-trading-scheduler -f

# Or check scheduled run logs
tail -f logs/cron-morning.log
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

- `src/trading_tools/position_tracker.py` - Core alert system
- `src/trading/trading_cycle.py` - Trading cycle integration
- `src/trading/position_manager.py` - Position management
- `main.py` - Main trading interface
- `tests/test_position_alerts.py` - Test suite

## References

- Issue #306: Position Management Enhancements
- Issue #321: Dynamic trailing stop logic
- TODO.md: System development roadmap
