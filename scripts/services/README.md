# Backtest Service

This directory contains the intelligent backtest service that handles API rate limits and manages long-running tests.

## Files

- `backtest_service.py` - Core service with rate limit management logic
- `start_backtest_service.py` - User-friendly manager interface
- `run_backtest_service.sh` - Shell wrapper with auto-restart capability

## Features

- **Automatic Rate Limit Management**: Tracks API usage and pauses when limits are hit
- **Resume Capability**: Saves progress and resumes from failures
- **Cost Tracking**: Monitors OpenAI API usage (GPT-4o-mini: ~$0.50/ticker/year)
- **Parallel Execution**: Runs multiple backtests efficiently
- **Progress Monitoring**: Real-time status updates with completion percentage
- **Graceful Shutdown**: Ctrl+C finishes current task before stopping

## Usage

### Start the Service

```bash
python scripts/backtest_service/start_backtest_service.py
```

Choose from the options:

1. Run in screen (recommended for remote servers)
2. Run in foreground
3. Run with nohup

### Monitor Progress

- Service progress: `.cache/backtests/service_progress.json`
- Service logs: `.cache/backtests/service.log`
- Market conditions progress: `.cache/backtests/market_conditions_progress.json`

### Stop the Service

- Screen: `screen -r backtest_service` then Ctrl+C
- Foreground: Ctrl+C
- Nohup: Find PID with `ps aux | grep backtest_service` then `kill -TERM <PID>`
