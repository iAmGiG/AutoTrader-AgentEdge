#!/bin/bash
# Setup crontab for AutoGen Trading System (alternative to systemd)
# Issue #287 - GTC Daily Execution

set -e

echo "=== AutoGen Trading Scheduler - Crontab Setup ==="
echo ""

# Configuration (edit for your install)
PROJECT_ROOT="$HOME/AutoTrader-AgentEdge"
PYTHON_BIN="$HOME/miniconda3/envs/AutoGex/bin/python"

# Check if project exists
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "ERROR: Project directory not found: $PROJECT_ROOT"
    exit 1
fi

# Check if Python environment exists
if [ ! -f "$PYTHON_BIN" ]; then
    echo "ERROR: Python binary not found: $PYTHON_BIN"
    echo "Please update PYTHON_BIN in this script"
    exit 1
fi

# Create the state directory (logs go there)
mkdir -p "$PROJECT_ROOT/state"

# One entry every 5 minutes: the scheduler itself decides what is due, in ET whatever
# the host timezone, on NYSE trading days only, within 5 minutes of each routine's time
# (config_defaults/scheduler_config.yaml), once per day. A lock in state/ stops a run
# from overlapping a long retry, the daemon, or a manual run.
# stdout duplicates state/scheduler.log (rotated), so only errors are kept
CRON_DUE="*/5 * * * * cd $PROJECT_ROOT && $PYTHON_BIN main.py --run-due > /dev/null 2>> $PROJECT_ROOT/state/scheduler-cron.err"

echo "Crontab entry to be added:"
echo ""
echo "# OptionsCommander - scheduler check (routines run when due)"
echo "$CRON_DUE"
echo ""

# Ask for confirmation
read -p "Add these entries to crontab? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

# Backup current crontab
crontab -l > "$PROJECT_ROOT/crontab.backup.$(date +%Y%m%d_%H%M%S)" 2>/dev/null || true

# Add entries to crontab
(crontab -l 2>/dev/null || true; echo ""; echo "# OptionsCommander - scheduler check (routines run when due)"; echo "$CRON_DUE") | crontab -

echo ""
echo "✅ Crontab entry added successfully!"
echo ""
echo "View crontab: crontab -l"
echo "Remove entry: crontab -e  (then delete the OptionsCommander lines)"
echo "Logs:"
echo "  Scheduler: $PROJECT_ROOT/state/scheduler.log (rotated)"
echo "  Cron errors: $PROJECT_ROOT/state/scheduler-cron.err"
echo ""
echo "Routines only run once the scheduler is enabled (CLI: /scheduler, or the setup wizard)."
echo "Don't also run the systemd service: either works, and the lock only prevents overlap."
