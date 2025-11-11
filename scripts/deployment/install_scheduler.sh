#!/bin/bash
# Installation script for AutoGen Trading Scheduler
# Issue #287 - GTC Daily Execution

set -e

echo "=== AutoGen Trading Scheduler Installation ==="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo)"
    exit 1
fi

# Configuration
SERVICE_NAME="autogen-trading-scheduler"
SERVICE_FILE="$SERVICE_NAME.service"
SYSTEMD_PATH="/etc/systemd/system/$SERVICE_FILE"
PROJECT_ROOT="/home/trader/AutoGen-TradingSystem"
USER="trader"
GROUP="trader"

echo "Configuration:"
echo "  Service name: $SERVICE_NAME"
echo "  Project root: $PROJECT_ROOT"
echo "  User: $USER"
echo "  Group: $GROUP"
echo ""

# Check if user exists
if ! id "$USER" &>/dev/null; then
    echo "ERROR: User '$USER' does not exist"
    echo "Create user first: sudo useradd -m -s /bin/bash trader"
    exit 1
fi

# Check if project directory exists
if [ ! -d "$PROJECT_ROOT" ]; then
    echo "ERROR: Project directory not found: $PROJECT_ROOT"
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/state"
mkdir -p "$PROJECT_ROOT/reports/daily"

# Set ownership
chown -R $USER:$GROUP "$PROJECT_ROOT/logs"
chown -R $USER:$GROUP "$PROJECT_ROOT/state"
chown -R $USER:$GROUP "$PROJECT_ROOT/reports"

# Copy service file
echo "Installing systemd service..."
cp "$(dirname "$0")/$SERVICE_FILE" "$SYSTEMD_PATH"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable service
echo "Enabling service to start on boot..."
systemctl enable $SERVICE_NAME

echo ""
echo "✅ Installation complete!"
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start $SERVICE_NAME"
echo "  Stop:    sudo systemctl stop $SERVICE_NAME"
echo "  Status:  sudo systemctl status $SERVICE_NAME"
echo "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
echo "  Disable: sudo systemctl disable $SERVICE_NAME"
echo ""
echo "Log files:"
echo "  Stdout:  $PROJECT_ROOT/logs/scheduler-stdout.log"
echo "  Stderr:  $PROJECT_ROOT/logs/scheduler-stderr.log"
echo ""
echo "To start the scheduler now, run:"
echo "  sudo systemctl start $SERVICE_NAME"
