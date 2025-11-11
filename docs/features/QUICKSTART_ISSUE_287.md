# Quick Start: GTC Daily Execution (Issue #287)

## What is it?

Automated "set it and forget it" daily trading system that:
- Runs twice daily (9:20 AM and 3:50 PM ET)
- Automatically adjusts stops based on profit levels
- Places GTC orders that broker manages
- Retries failed operations automatically
- Uses only 3-5 API calls per routine (90% cost savings)

## 5-Minute Setup

### 1. Test the Scheduler

```bash
# Navigate to project root
cd ~/AutoGen-TradingSystem

# Activate environment
conda activate RH2MAS

# Test morning routine (dry run)
python src/trading/daily_scheduler.py --mode once --task morning_routine
```

Expected output:
```
✅ morning_routine completed successfully
Task: morning_routine | Status: completed | Duration: 12.3s | Attempt: 1 | API Calls: 3
```

### 2. Review Configuration

```bash
# View configuration
cat config_defaults/scheduler_config.json
```

Edit if needed:
```json
{
  "enabled": true,
  "morning_routine_time": "09:20:00",  # Adjust timing if needed
  "evening_routine_time": "15:50:00",
  "max_retries": 3
}
```

### 3. Choose Deployment Method

**Option A: systemd (Recommended for servers)**

```bash
# Install as service
sudo scripts/deployment/install_scheduler.sh

# Start service
sudo systemctl start autogen-trading-scheduler

# Check status
sudo systemctl status autogen-trading-scheduler

# View live logs
sudo journalctl -u autogen-trading-scheduler -f
```

**Option B: crontab (Simple alternative)**

```bash
# Setup cron jobs
./scripts/deployment/setup_cron.sh

# Verify
crontab -l

# View logs
tail -f logs/cron-morning.log
```

**Option C: Manual (For testing)**

```bash
# Run as daemon in terminal
python src/trading/daily_scheduler.py --mode daemon --interval 60
```

### 4. Monitor Execution

**View status report:**
```bash
python src/trading/daily_scheduler.py --mode status
```

**Check execution log:**
```bash
cat state/scheduler_execution_log.json | jq '.'
```

**View daily reports:**
```bash
ls -lh reports/daily/
cat reports/daily/$(ls -t reports/daily/ | head -1)
```

## What Happens Automatically?

### Morning Routine (9:20 AM ET)
1. ✅ Fetch all positions from broker (1 API call)
2. ✅ Fetch all open orders (1 API call)
3. ✅ Reconcile any discrepancies
4. ✅ Calculate stop adjustments based on profit:
   - Under 2% profit: No adjustment
   - 2-4% profit: Move to breakeven
   - 4-6% profit: Lock in 25% of gains
   - Over 6% profit: Trail at 50% of gains
5. ✅ Batch modify stops if needed (1 API call)
6. ✅ Generate morning report
7. ✅ Total: 3-5 API calls, 10-30 seconds

### Evening Routine (3:50 PM ET)
1. ✅ Review end-of-day positions
2. ✅ Reconcile with broker
3. ✅ Generate evening report
4. ✅ Prepare for next trading day
5. ✅ Total: 3 API calls, 10-20 seconds

## Error Handling

The system automatically handles:
- **API errors**: Retries with exponential backoff (60s, 120s, 240s)
- **Network failures**: Retries up to 3 times
- **Broker discrepancies**: Auto-reconciles with broker-as-truth
- **Crashed state**: Recovery mode rebuilds from broker

If all retries fail, you get:
- Detailed error log in `state/scheduler.log`
- Failed execution entry in `state/scheduler_execution_log.json`
- System continues and tries again next scheduled time

## Stopping/Pausing

**Temporary pause (keep service running):**
```bash
# Edit config
nano config_defaults/scheduler_config.json
# Set: "enabled": false

# Service will continue but skip executions
```

**Stop service:**
```bash
# systemd
sudo systemctl stop autogen-trading-scheduler

# cron
crontab -e  # Delete the AutoGen lines

# daemon
Ctrl+C in terminal
```

## Cost Comparison

| Approach | API Calls/Day | Monthly Cost* |
|----------|---------------|---------------|
| Traditional polling | 1,000+ | $50-100 |
| GTC with daily checks | 6-10 | $5-10 |
| **This system** | **6-10** | **$5-10** |

*Estimated based on typical API pricing

## Troubleshooting

**Scheduler not running:**
```bash
# Check service status
sudo systemctl status autogen-trading-scheduler

# View recent errors
sudo journalctl -u autogen-trading-scheduler -n 50
```

**Tasks not executing:**
```bash
# Verify timezone
timedatectl

# Should show: America/New_York
# If not: sudo timedatectl set-timezone America/New_York

# Check if already ran today
cat state/scheduler_execution_log.json | jq '.[-5:]'
```

**Need to run manually:**
```bash
# Morning routine
python src/trading/daily_scheduler.py --mode once --task morning_routine

# Evening routine
python src/trading/daily_scheduler.py --mode once --task evening_routine

# Both
python src/trading/daily_scheduler.py --mode once
```

## Next Steps

1. **Monitor for 1 week**: Let it run and review daily reports
2. **Verify stop adjustments**: Check that stops move correctly
3. **Review execution log**: Ensure 100% success rate
4. **Customize schedule**: Adjust times in `scheduler_config.json` if needed
5. **Integrate with VoterAgent**: Use `automated_trading.py` for signal generation

## Advanced Usage

### With VoterAgent Integration

```bash
# Run complete automated trading
python src/trading/automated_trading.py --mode paper --watchlist SPY TQQQ QQQ
```

This combines:
- Morning routine (reconcile, adjust stops)
- VoterAgent signal generation
- Automated order placement
- Evening routine (review)

### Custom Watchlist

Edit `config_defaults/scheduler_config.json`:
```json
{
  "watchlist": ["AAPL", "MSFT", "GOOGL", "NVDA"],
  "min_confidence": 0.70
}
```

### Notifications (Future)

```json
{
  "enable_notifications": true,
  "notification_channels": {
    "email": "trader@example.com",
    "telegram": "@tradingbot"
  }
}
```

## Documentation

- **Full documentation**: `docs/features/issue_287_gtc_daily_execution.md`
- **Trading cycle details**: `src/trading/trading_cycle.py`
- **Scheduler implementation**: `src/trading/daily_scheduler.py`
- **Tests**: `tests/test_daily_scheduler.py`

## Support

Issues or questions:
- GitHub Issues: https://github.com/iAmGiG/AutoGen-TradingSystem/issues
- Documentation: `docs/features/issue_287_gtc_daily_execution.md`
- Examples: `scripts/deployment/`

---

**You're now running automated daily trading! 🚀**

Monitor the logs, review the reports, and let the system handle the routine work while you focus on strategy.
