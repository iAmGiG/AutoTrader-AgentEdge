#!/usr/bin/env python3
"""Start backtest service in background with monitoring.

This provides a simple way to run the backtest service with:
- Progress monitoring
- Graceful shutdown
- Auto-resume on failure
"""

import subprocess
import os
import time
import json
from datetime import datetime


def check_service_status():
    """Check if service is already running."""
    try:
        # Check if there's a recent progress file
        progress_file = ".cache/backtests/service_progress.json"
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                progress = json.load(f)

            last_run = progress.get('last_run')
            if last_run:
                last_time = datetime.fromisoformat(last_run)
                time_diff = (datetime.now() - last_time).total_seconds()

                if time_diff < 300:  # Active in last 5 minutes
                    completed = len(progress.get('completed', []))
                    total = 40  # 5 conditions * 8 tickers
                    percent = (completed / total) * 100
                    return True, f"Service active: {completed}/{total} ({percent:.1f}%) completed"

        return False, "Service not running"
    except:
        return False, "Service not running"


def start_service(background=True):
    """Start the backtest service."""
    if background:
        print("Starting backtest service in background...")
        print("\nOptions:")
        print("1. Run in screen (recommended)")
        print("2. Run in current terminal")
        print("3. Run with nohup")

        choice = input("\nSelect option (1-3): ").strip()

        if choice == "1":
            # Run in screen
            cmd = [
                "screen", "-dmS", "backtest_service",
                "bash", "scripts/run_backtest_service.sh"
            ]
            subprocess.run(cmd)
            print("\n✅ Service started in screen session 'backtest_service'")
            print("Commands:")
            print("  View logs:    screen -r backtest_service")
            print("  Detach:       Ctrl+A, D")
            print("  Stop service: Ctrl+C (while attached)")

        elif choice == "2":
            # Run in current terminal
            subprocess.run(["bash", "scripts/run_backtest_service.sh"])

        elif choice == "3":
            # Run with nohup
            with open(".cache/backtests/nohup.out", "w") as out:
                subprocess.Popen(
                    ["python", "scripts/backtest_service.py"],
                    stdout=out,
                    stderr=out,
                    start_new_session=True
                )
            print("\n✅ Service started with nohup")
            print("View logs: tail -f .cache/backtests/nohup.out")
    else:
        # Run directly
        subprocess.run(["python", "scripts/backtest_service.py"])


def monitor_progress():
    """Monitor service progress."""
    print("\n📊 Monitoring backtest progress...\n")

    try:
        while True:
            is_running, status = check_service_status()

            if os.path.exists(".cache/backtests/service_progress.json"):
                with open(".cache/backtests/service_progress.json", 'r') as f:
                    progress = json.load(f)

                completed = len(progress.get('completed', []))
                failed = len(progress.get('failed', []))
                total = 40  # 5 conditions * 8 tickers
                percent = (completed / total) * 100

                openai_cost = progress.get('openai_total_cost', 0.0)
                print(f"\r{datetime.now().strftime('%H:%M:%S')} - "
                      f"Progress: {completed}/{total} ({percent:.1f}%) "
                      f"| Failed: {failed} "
                      f"| API Errors: {progress.get('api_errors', 0)} "
                      f"| OpenAI: ${openai_cost:.2f} "
                      f"| {status}", end='', flush=True)

                if completed == total:
                    print("\n\n✅ All backtests completed!")
                    break
            else:
                print(f"\r{datetime.now().strftime('%H:%M:%S')} - "
                      f"Waiting for service to start...", end='', flush=True)

            time.sleep(10)  # Update every 10 seconds

    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")


def main():
    """Main entry point."""
    print("""
╔══════════════════════════════════════════════════════════╗
║        RH2MAS Backtest Service Manager                   ║
╚══════════════════════════════════════════════════════════╝
    """)

    # Check if service is running
    is_running, status = check_service_status()

    if is_running:
        print(f"ℹ️  {status}")
        print("\nOptions:")
        print("1. Monitor progress")
        print("2. View logs")
        print("3. Exit")

        choice = input("\nSelect option (1-3): ").strip()

        if choice == "1":
            monitor_progress()
        elif choice == "2":
            log_file = ".cache/backtests/service.log"
            if os.path.exists(log_file):
                subprocess.run(["tail", "-f", log_file])
    else:
        print("ℹ️  Service not running")
        print("\nOptions:")
        print("1. Start service")
        print("2. View previous results")
        print("3. Exit")

        choice = input("\nSelect option (1-3): ").strip()

        if choice == "1":
            start_service()
            time.sleep(2)
            monitor_progress()
        elif choice == "2":
            if os.path.exists(".cache/backtests/service_progress.json"):
                with open(".cache/backtests/service_progress.json", 'r') as f:
                    progress = json.load(f)
                print(f"\nPrevious run completed: {len(progress.get('completed', []))} tasks")
                print(f"Failed: {len(progress.get('failed', []))}")


if __name__ == "__main__":
    main()
