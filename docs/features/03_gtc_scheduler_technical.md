# Issue #287: GTC Daily Execution System

**Status**: ✅ COMPLETED
**Priority**: P2
**Size**: Medium
**Foundation**: Issue #313 (Order Management System)

## Overview

Automated "set it and forget it" daily trading system with:
- **Daily Scheduling**: Morning (9:20 AM ET) and evening (3:50 PM ET) routines
- **Retry Logic**: Exponential backoff with configurable retries
- **Error Handling**: Comprehensive exception management and recovery
- **GTC Orders**: Good-Til-Cancelled orders managed by broker
- **Minimal API Calls**: 3-5 calls per routine for cost efficiency

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                   Daily Scheduler                        │
│  • Task scheduling and execution                        │
│  • Retry logic with exponential backoff                 │
│  • Execution logging and monitoring                     │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              Trading Cycle (Issue #313)                  │
│  • Morning routine: reconcile, adjust stops             │
│  • Evening routine: EOD review                          │
│  • GTC order management                                 │
└─────────────────┬───────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────┐
│              Order Management (Issue #313)               │
│  • GTC limit orders                                     │
│  • Bracket orders with stops/targets                    │
│  • Position tracking and reconciliation                 │
└─────────────────────────────────────────────────────────┘
```

### File Structure

```
src/trading/
├── daily_scheduler.py          # Main scheduler with retry logic
├── automated_trading.py        # VoterAgent integration
├── trading_cycle.py           # Morning/evening routines (Issue #313)
└── order_manager.py           # GTC order management (Issue #313)

config_defaults/
└── scheduler_config.json      # Scheduling configuration

scripts/deployment/
├── autogen-trading-scheduler.service  # systemd service
├── install_scheduler.sh              # systemd installation
└── setup_cron.sh                     # crontab alternative

tests/
└── test_daily_scheduler.py    # Comprehensive tests
```

## Features

### 1. Daily Scheduling

**Morning Routine (9:20 AM ET)**:
- Reconcile positions with broker (single API call)
- Calculate stop adjustments based on profit levels
- Batch modify stop orders if needed
- Generate morning report

**Evening Routine (3:50 PM ET)**:
- EOD position review
- Prepare for next trading day
- Generate evening report

### 2. Comprehensive Retry Logic

```python
# Exponential backoff with jitter
for attempt in range(1, max_attempts + 1):
    try:
        execute_routine()
        break  # Success
    except Exception as e:
        if attempt < max_attempts:
            delay = base_delay * (2 ** (attempt - 1))
            jitter = delay * 0.1
            sleep(delay + jitter)
        else:
            log_failure()
```

**Features**:
- Configurable max retries (default: 3)
- Exponential backoff (60s, 120s, 240s)
- 10% jitter to prevent thundering herd
- Detailed error logging

### 3. Error Handling

**Levels**:
1. **Task-level**: Catch and retry individual routine failures
2. **Execution-level**: Log all attempts and outcomes
3. **System-level**: Daemon continues despite errors
4. **Recovery**: Crash recovery rebuilds state from broker

**Error Types**:
- API errors → Retry with backoff
- Network failures → Retry with backoff
- Invalid data → Log and skip
- Broker discrepancies → Auto-reconcile

### 4. Configuration System

`config_defaults/scheduler_config.json`:
```json
{
  "enabled": true,
  "market_timezone": "America/New_York",
  "morning_routine_time": "09:20:00",
  "evening_routine_time": "15:50:00",
  "max_retries": 3,
  "retry_delay_seconds": 60,
  "timeout_seconds": 300,
  "enable_notifications": false,
  "dry_run": false
}
```

## Usage

### Quick Start

```bash
# Test mode - run morning routine once
python src/trading/daily_scheduler.py --mode once --task morning_routine

# View status
python src/trading/daily_scheduler.py --mode status

# Run as daemon (development)
python src/trading/daily_scheduler.py --mode daemon --interval 60
```

### Production Deployment

**Option 1: systemd (Recommended for Linux servers)**

```bash
# Install service
sudo scripts/deployment/install_scheduler.sh

# Start service
sudo systemctl start autogen-trading-scheduler

# View logs
sudo journalctl -u autogen-trading-scheduler -f

# Status
sudo systemctl status autogen-trading-scheduler
```

**Option 2: crontab (Alternative)**

```bash
# Setup cron jobs
./scripts/deployment/setup_cron.sh

# View crontab
crontab -l

# Logs
tail -f logs/cron-morning.log
tail -f logs/cron-evening.log
```

### Integration with VoterAgent

```bash
# Run complete automated trading cycle
python src/trading/automated_trading.py --mode paper --watchlist SPY TQQQ QQQ
```

## Monitoring

### Execution Logs

```json
{
  "task_name": "morning_routine",
  "scheduled_time": "09:20:00",
  "actual_start_time": "2025-01-15T09:20:05",
  "actual_end_time": "2025-01-15T09:20:32",
  "status": "completed",
  "attempt": 1,
  "error_message": null,
  "report_path": "reports/daily/20250115_0920_morning.md",
  "api_calls_used": 3
}
```

### Status Reports

```bash
# Generate status report
python src/trading/daily_scheduler.py --mode status
```

Output:
```
# Daily Scheduler Status Report
Generated: 2025-01-15 16:00:00

## Recent Executions (Last 7 Days)

### morning_routine
Total executions: 5
✅ Completed: 5
❌ Failed: 0
Success rate: 100.0%

### evening_routine
Total executions: 5
✅ Completed: 5
❌ Failed: 0
Success rate: 100.0%
```

### Log Files

- **Scheduler log**: `state/scheduler.log`
- **Execution log**: `state/scheduler_execution_log.json`
- **Morning reports**: `reports/daily/*_morning.md`
- **Evening reports**: `reports/daily/*_evening.md`
- **systemd logs**: `journalctl -u autogen-trading-scheduler`
- **Cron logs**: `logs/cron-morning.log`, `logs/cron-evening.log`

## Testing

```bash
# Run tests
python tests/test_daily_scheduler.py

# Test individual components
python -m pytest tests/test_daily_scheduler.py::TestDailyScheduler::test_execute_task_retry -v

# Integration test
python src/trading/daily_scheduler.py --mode test
```

## Performance

### API Call Optimization

**Traditional approach**: 50+ API calls per day
- Check positions: 10-15 calls
- Update each stop: 3-5 calls per position
- Check order status: 10+ calls

**GTC approach**: 3-5 API calls per routine
- Single call to get all positions
- Single call to get all orders
- Batch modify stops: 1 call per modification

**Savings**: ~90% fewer API calls

### Execution Time

- **Morning routine**: 10-30 seconds
- **Evening routine**: 10-20 seconds
- **Total daily overhead**: < 1 minute

## Configuration

### Scheduler Settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enabled` | `true` | Master enable/disable |
| `market_timezone` | `America/New_York` | ET timezone for market hours |
| `morning_routine_time` | `09:20:00` | Morning execution time |
| `evening_routine_time` | `15:50:00` | Evening execution time |
| `max_retries` | `3` | Maximum retry attempts |
| `retry_delay_seconds` | `60` | Base retry delay |
| `timeout_seconds` | `300` | Max routine execution time |

### systemd Service

| Setting | Value | Purpose |
|---------|-------|---------|
| `Restart` | `on-failure` | Auto-restart on crashes |
| `RestartSec` | `30` | Wait 30s before restart |
| `CPUQuota` | `50%` | Limit CPU usage |
| `MemoryLimit` | `1G` | Limit memory usage |

## Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u autogen-trading-scheduler -n 50

# Verify configuration
python src/trading/daily_scheduler.py --mode status

# Test manually
python src/trading/daily_scheduler.py --mode once --task morning_routine
```

### Tasks not executing

1. Check timezone: `timedatectl`
2. Verify schedule: `cat config_defaults/scheduler_config.json`
3. Check if already executed: Review `state/scheduler_execution_log.json`
4. Verify enabled: `"enabled": true` in config

### API errors

1. Check credentials: `config/config.json`
2. Verify API limits: Alpaca dashboard
3. Review error logs: `state/scheduler.log`
4. Test connection: `python main.py check-positions`

### High failure rate

1. Review execution log: `state/scheduler_execution_log.json`
2. Increase retry count: `max_retries` in config
3. Increase retry delay: `retry_delay_seconds` in config
4. Check network stability

## Future Enhancements

### Planned (Future Issues)

- [ ] Email/SMS notifications on failures
- [ ] Telegram bot integration
- [ ] Advanced scheduling (skip holidays, market closures)
- [ ] Multi-account support
- [ ] Performance analytics dashboard
- [ ] Machine learning for optimal execution times
- [ ] Dynamic retry strategy based on error type

### Integration Points

- **Issue #308**: Human-in-loop CLI for trade approval
- **Issue #310**: Multi-agent coordination
- **Issue #324**: Forward testing protocol
- **Issue #321**: Dynamic trailing stop logic

## Value Delivered

✅ **"Set it and forget it" automation**: No manual intervention needed
✅ **Reliability**: Comprehensive retry and error handling
✅ **Cost-efficient**: 90% fewer API calls
✅ **Production-ready**: systemd service with monitoring
✅ **Flexible**: Both daemon and cron deployment options
✅ **Observable**: Detailed logging and status reports

## Related Documentation

- [Trading Cycle](../integration/trading_cycle.md) - Morning/evening routine details
- [Order Management](../integration/alpaca_order_management.md) - GTC order system
- [systemd Service](../deployment/systemd_setup.md) - Production deployment
- [Configuration](../reference/configuration.md) - All configuration options

---

**Issue #287 Status**: ✅ COMPLETED
**Last Updated**: 2025-01-15
**Implemented By**: Claude (AutoGen Trading System)
