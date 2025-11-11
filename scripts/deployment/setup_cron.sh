#!/bin/bash
# Setup crontab for AutoGen Trading System (alternative to systemd)
# Issue #287 - GTC Daily Execution

set -e

echo "=== AutoGen Trading Scheduler - Crontab Setup ==="
echo ""

# Configuration
PROJECT_ROOT="$HOME/AutoGen-TradingSystem"
PYTHON_BIN="$HOME/anaconda3/envs/RH2MAS/bin/python"
SCHEDULER_SCRIPT="$PROJECT_ROOT/src/trading/daily_scheduler.py"
LOG_DIR="$PROJECT_ROOT/logs"

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

# Create log directory
mkdir -p "$LOG_DIR"

# Create crontab entries
CRON_MORNING="20 9 * * 1-5 cd $PROJECT_ROOT && $PYTHON_BIN $SCHEDULER_SCRIPT --mode once --task morning_routine >> $LOG_DIR/cron-morning.log 2>&1"
CRON_EVENING="50 15 * * 1-5 cd $PROJECT_ROOT && $PYTHON_BIN $SCHEDULER_SCRIPT --mode once --task evening_routine >> $LOG_DIR/cron-evening.log 2>&1"

echo "Crontab entries to be added:"
echo ""
echo "# AutoGen Trading System - Morning Routine (9:20 AM ET, Mon-Fri)"
echo "$CRON_MORNING"
echo ""
echo "# AutoGen Trading System - Evening Routine (3:50 PM ET, Mon-Fri)"
echo "$CRON_EVENING"
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
(crontab -l 2>/dev/null || true; echo ""; echo "# AutoGen Trading System - Morning Routine (9:20 AM ET, Mon-Fri)"; echo "$CRON_MORNING"; echo ""; echo "# AutoGen Trading System - Evening Routine (3:50 PM ET, Mon-Fri)"; echo "$CRON_EVENING") | crontab -

echo ""
echo "✅ Crontab entries added successfully!"
echo ""
echo "View crontab: crontab -l"
echo "Remove entries: crontab -e  (then delete the AutoGen lines)"
echo "Logs:"
echo "  Morning: $LOG_DIR/cron-morning.log"
echo "  Evening: $LOG_DIR/cron-evening.log"
echo ""
echo "IMPORTANT: Make sure your system timezone is set to ET (America/New_York)"
echo "Check with: timedatectl | grep 'Time zone'"
echo "Set with:   sudo timedatectl set-timezone America/New_York"
