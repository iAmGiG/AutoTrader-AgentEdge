#!/bin/bash
# Run backtest service with automatic restart on failure

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate conda environment if available
if command -v conda &> /dev/null; then
    echo "Activating conda environment..."
    source $(conda info --base)/etc/profile.d/conda.sh
    conda activate AutoGen 2>/dev/null || echo "AutoGen environment not found"
fi

# Create required directories
mkdir -p .cache/backtests/runs
mkdir -p reports/advisor/market_analysis

echo "Starting Backtest Service..."
echo "Logs: .cache/backtests/service.log"
echo "Progress: .cache/backtests/service_progress.json"
echo ""

# Run with automatic restart
while true; do
    python scripts/backtest_service.py
    
    if [ $? -eq 0 ]; then
        echo "Service completed successfully"
        break
    else
        echo "Service crashed, restarting in 60 seconds..."
        sleep 60
    fi
done