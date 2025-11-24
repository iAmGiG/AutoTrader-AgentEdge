"""
Scheduler CLI - Interactive scheduler management interface.

Provides dedicated commands for:
- Viewing scheduler status with detailed breakdown
- Editing scheduler configuration interactively
- Testing scheduler routines
- Monitoring execution history
- Starting/stopping scheduler service
"""

import asyncio
import logging
import os

# TODO: utilize @date_utils.py for more datetime lib usage.
from datetime import time as dt_time
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None


from src.trading.daily_scheduler import DailyScheduler

logger = logging.getLogger(__name__)


class SchedulerCLI:
    """
    Interactive CLI for scheduler management.

    Provides a dedicated interface for managing the daily trading scheduler,
    separate from the main trading CLI.
    """

    def __init__(self, scheduler: Optional[DailyScheduler] = None):
        """
        Initialize scheduler CLI.

        Args:
            scheduler: Optional existing DailyScheduler instance
        """
        self.scheduler = scheduler
        self.config_file = "config_defaults/scheduler_config.yaml"

        # Check for YAML, fallback to JSON
        if not os.path.exists(self.config_file):
            self.config_file = "config_defaults/scheduler_config.json"

    async def run(self):
        """
        Main scheduler CLI loop.

        Provides interactive menu for scheduler management.
        """
        self._print_welcome()

        while True:
            try:
                command = input("\nScheduler> ").strip().lower()

                if not command:
                    continue

                # Strip leading slash for compatibility with main CLI
                if command.startswith("/"):
                    command = command[1:]

                if command in ["exit", "quit", "q"]:
                    print("\n👋 Exiting scheduler CLI...")
                    break

                await self._handle_command(command)

            except KeyboardInterrupt:
                print("\n\n👋 Exiting scheduler CLI...")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                logger.error(f"Scheduler CLI error: {e}", exc_info=True)

    def _print_welcome(self):
        """Print scheduler CLI welcome message."""
        print("\n" + "=" * 70)
        print("   📅 Scheduler Management CLI")
        print("=" * 70)
        print("\nCommands:")
        print("  status          - Show detailed scheduler status")
        print("  config          - View current configuration")
        print("  info            - Explain configuration settings")
        print("  edit            - Edit scheduler configuration")
        print("  enable          - Enable scheduler")
        print("  disable         - Disable scheduler")
        print("  test morning    - Test morning routine")
        print("  test evening    - Test evening routine")
        print("  history         - View execution history")
        print("  next            - Show next scheduled run")
        print("  help            - Show this help message")
        print("  exit            - Exit scheduler CLI")
        print("")

    async def _handle_command(self, command: str):
        """
        Handle scheduler CLI commands.

        Args:
            command: User command string
        """
        # Initialize scheduler if needed
        if self.scheduler is None and command not in ["help", "config", "edit"]:
            try:
                self.scheduler = DailyScheduler()
            except Exception as e:
                print(f"❌ Failed to initialize scheduler: {e}")
                print("💡 Try running: python main.py --daemon")
                return

        if command == "help":
            self._print_welcome()

        elif command == "status":
            await self._show_status()

        elif command == "config":
            self._show_config()

        elif command == "info":
            self._show_config_info()

        elif command == "edit":
            await self._edit_config()

        elif command == "enable":
            self._set_enabled(True)

        elif command == "disable":
            self._set_enabled(False)

        elif command.startswith("test"):
            parts = command.split()
            if len(parts) == 2 and parts[1] in ["morning", "evening"]:
                await self._test_routine(parts[1])
            else:
                print("Usage: test [morning|evening]")

        elif command == "history":
            self._show_history()

        elif command == "next":
            self._show_next_run()

        else:
            print(f"Unknown command: {command}")
            print("Type 'help' for available commands")

    async def _show_status(self):
        """Show detailed scheduler status."""
        print("\n⏰ Scheduler Status")
        print("=" * 70)

        if not self.scheduler:
            print("❌ Scheduler not initialized")
            return

        # Check if daemon is actually running
        daemon_running = self._is_daemon_running()
        enabled = self.scheduler.config.get("enabled", False)

        # Config status
        config_emoji = "🟢" if enabled else "🔴"
        print(f"\n{config_emoji} Config: {'ENABLED' if enabled else 'DISABLED'}")

        # Daemon/service status (actual execution)
        if daemon_running:
            print("✅ Service: RUNNING (automatic execution active)")
        else:
            print("❌ Service: NOT RUNNING (no automatic execution)")
            if enabled:
                print("\n💡 Config is enabled but daemon is not running.")
                print("   To start automatic execution:")
                print("   1. Exit this CLI")
                print("   2. Run: python main.py --daemon")
                print("   3. Scheduler will run automatically at scheduled times")
                print("\n   Or use 'test morning/evening' to run manually now")

        print("\n⚙️  Configuration:")
        print(f"   Morning: {self.scheduler.config.get('morning_routine_time', 'N/A')} ET")
        print(f"   Evening: {self.scheduler.config.get('evening_routine_time', 'N/A')} ET")
        print(f"   Timezone: {self.scheduler.config.get('market_timezone', 'N/A')}")
        print(f"   Max Retries: {self.scheduler.config.get('max_retries', 3)}")
        print(f"   Dry Run: {self.scheduler.config.get('dry_run', False)}")

        # Show recent executions
        recent = self.scheduler.get_execution_history(days=1)
        if recent:
            print(f"\n📋 Today's Executions: {len(recent)}")
            for entry in recent[:5]:
                status = "✅" if entry.status == "completed" else "❌"
                print(f"   {status} {entry.task_name} - {entry.status}")
        else:
            print("\n📋 No executions today")
            if enabled and not daemon_running:
                print("   (Daemon not running - no automatic executions)")

    def _is_daemon_running(self) -> bool:
        """Check if scheduler daemon is actually running."""
        # Try psutil first (if available)
        try:
            import psutil

            # Check for process running main.py --daemon
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info.get("cmdline", [])
                    if cmdline and "main.py" in " ".join(cmdline) and "--daemon" in cmdline:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except (ImportError, Exception):
            # psutil not installed or error, use PID file fallback
            pass

        # Fallback: Check PID file
        pid_file = Path("state/scheduler.pid")
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text())
                os.kill(pid, 0)  # Check if process exists (0 = no signal, just check)
                return True
            except (OSError, ValueError):
                # Process doesn't exist or PID file corrupted
                pass

        return False

    def _show_config(self):
        """Display current scheduler configuration."""
        print("\n⚙️  Scheduler Configuration")
        print("=" * 70)

        if os.path.exists(self.config_file):
            print(f"\nConfig file: {self.config_file}\n")
            with open(self.config_file, "r") as f:
                content = f.read()
                print(content)
        else:
            print(f"❌ Config file not found: {self.config_file}")
            print("💡 Will be created with defaults on first run")

    def _show_config_info(self):
        """Display explanations for configuration settings."""
        print("\n📖 Scheduler Configuration Guide")
        print("=" * 70)

        print("\n🔧 EDITABLE SETTINGS")
        print("-" * 70)

        print("\n1. enabled (boolean)")
        print(
            "   Current: {}".format(
                self.scheduler.config.get("enabled", "N/A") if self.scheduler else "N/A"
            )
        )
        print("   Purpose: Master switch for automated trading")
        print("   Values:  true = scheduler runs automatically")
        print("            false = scheduler paused (safe mode)")
        print("   Tip:     Set to 'false' when testing or during holidays")

        print("\n2. morning_routine_time (HH:MM:SS)")
        print(
            "   Current: {}".format(
                self.scheduler.config.get("morning_routine_time", "N/A")
                if self.scheduler
                else "N/A"
            )
        )
        print("   Purpose: Daily pre-market check and position setup")
        print("   Default: 09:20:00 (9:20 AM ET, 10 min before market open)")
        print("   Tip:     Run before market opens to prepare for trading day")

        print("\n3. evening_routine_time (HH:MM:SS)")
        print(
            "   Current: {}".format(
                self.scheduler.config.get("evening_routine_time", "N/A")
                if self.scheduler
                else "N/A"
            )
        )
        print("   Purpose: End-of-day position review and trailing stop adjustments")
        print("   Default: 15:50:00 (3:50 PM ET, 10 min before market close)")
        print("   Tip:     Run before market closes to lock in profits")

        print("\n4. max_retries (integer 1-10)")
        print(
            "   Current: {}".format(
                self.scheduler.config.get("max_retries", "N/A") if self.scheduler else "N/A"
            )
        )
        print("   Purpose: Number of retry attempts if routine fails")
        print("   Default: 3")
        print("   Tip:     Higher values = more resilient to network issues")

        print("\n5. dry_run (boolean)")
        print(
            "   Current: {}".format(
                self.scheduler.config.get("dry_run", "N/A") if self.scheduler else "N/A"
            )
        )
        print("   Purpose: Test mode - simulates actions without placing orders")
        print("   Values:  true = simulation only (NO real orders)")
        print("            false = normal operation (places orders)")
        print("   ⚠️  NOTE: dry_run enforcement is NOT YET IMPLEMENTED")
        print("   Status:  Currently logs but doesn't prevent order execution")
        print("   Tip:     Always use paper trading account for testing")

        print("\n\n📋 READ-ONLY SETTINGS (edit config file directly)")
        print("-" * 70)

        print("\n• market_timezone: America/New_York")
        print("  All times are in Eastern Time (NYSE timezone)")

        print("\n• retry_delay_seconds: 60")
        print("  Initial wait time between retries (uses exponential backoff)")

        print("\n• timeout_seconds: 300")
        print("  Maximum time (5 minutes) for a single routine execution")

        print("\n• monitoring.alert_threshold_consecutive_failures: 2")
        print("  Number of consecutive failures before raising alert")

        print("\n• api_limits.max_calls_per_routine: 5")
        print("  Maximum API calls per routine to stay within rate limits")

        print("\n\n💡 QUICK REFERENCE")
        print("-" * 70)
        print("\nPaper Trading vs Dry Run:")
        print("  • Paper Trading (mode='paper'): Places real test orders on Alpaca paper account")
        print("  • Dry Run (dry_run=true): Simulates logic without any orders [NOT IMPLEMENTED]")
        print("  • Current system uses: Paper trading account (hardcoded in trading_cycle.py)")

        print("\nSafety Levels (intended design):")
        print("  1. Live mode + dry_run=false  → Real money, real orders ⚠️")
        print("  2. Paper mode + dry_run=false → Paper account, test orders ✅ (current)")
        print("  3. Paper mode + dry_run=true  → No orders, just logging 📝 (not implemented)")

        print("\nRelated Issues:")
        print("  • #369 - Advanced documentation/man command")
        print("  • #370 - LLM-powered trade journaling")

        print("\n" + "=" * 70)
        print("Type 'edit' to modify settings or 'config' to view raw file")
        print("")

    async def _edit_config(self):
        """Interactive configuration editor."""
        print("\n📝 Scheduler Configuration Editor")
        print("=" * 70)

        # Load current config
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                if self.config_file.endswith(".yaml") or self.config_file.endswith(".yml"):
                    if yaml is None:
                        print("❌ PyYAML not installed. Install with: pip install pyyaml")
                        return
                    config = yaml.safe_load(f)
                else:
                    import json

                    config = json.load(f)
        else:
            config = self._get_default_config()

        print("\nCurrent settings:")
        print(f"  1. Enabled: {config.get('enabled', True)}")
        print(f"  2. Morning routine: {config.get('morning_routine_time', '09:20:00')}")
        print(f"  3. Evening routine: {config.get('evening_routine_time', '15:50:00')}")
        print(f"  4. Max retries: {config.get('max_retries', 3)}")
        print(f"  5. Dry run mode: {config.get('dry_run', False)}")
        print("  0. Save and exit")
        print("  q. Cancel")

        while True:
            choice = input("\nEdit setting (1-5, 0 to save, q to cancel): ").strip()

            if choice == "q":
                print("Cancelled")
                return
            elif choice == "0":
                # Save config
                self._save_config(config)
                print("✅ Configuration saved!")

                # Reload scheduler if running
                if self.scheduler:
                    print("🔄 Reloading scheduler...")
                    # Reuse existing trading_cycle to avoid creating duplicate Alpaca clients
                    existing_cycle = self.scheduler.trading_cycle
                    self.scheduler = DailyScheduler(self.config_file, trading_cycle=existing_cycle)
                    print("✅ Scheduler reloaded")
                break
            elif choice == "1":
                value = input("Enable scheduler? (yes/no): ").strip().lower()
                config["enabled"] = value in ["yes", "y", "true"]
            elif choice == "2":
                value = input("Morning routine time (HH:MM:SS): ").strip()
                try:
                    dt_time.fromisoformat(value)  # Validate
                    config["morning_routine_time"] = value
                except ValueError:
                    print("❌ Invalid time format. Use HH:MM:SS")
            elif choice == "3":
                value = input("Evening routine time (HH:MM:SS): ").strip()
                try:
                    dt_time.fromisoformat(value)  # Validate
                    config["evening_routine_time"] = value
                except ValueError:
                    print("❌ Invalid time format. Use HH:MM:SS")
            elif choice == "4":
                value = input("Max retries (1-10): ").strip()
                try:
                    retries = int(value)
                    if 1 <= retries <= 10:
                        config["max_retries"] = retries
                    else:
                        print("❌ Value must be between 1 and 10")
                except ValueError:
                    print("❌ Invalid number")
            elif choice == "5":
                value = input("Enable dry run mode? (yes/no): ").strip().lower()
                config["dry_run"] = value in ["yes", "y", "true"]
            else:
                print("Invalid choice")

    def _save_config(self, config: dict):
        """Save configuration to file."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

        with open(self.config_file, "w") as f:
            if self.config_file.endswith(".yaml") or self.config_file.endswith(".yml"):
                if yaml is None:
                    raise ImportError("PyYAML not installed")
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
            else:
                import json

                json.dump(config, f, indent=2)

    def _get_default_config(self) -> dict:
        """Get default scheduler configuration."""
        return {
            "enabled": True,
            "market_timezone": "America/New_York",
            "morning_routine_time": "09:20:00",
            "evening_routine_time": "15:50:00",
            "max_retries": 3,
            "retry_delay_seconds": 60,
            "timeout_seconds": 300,
            "enable_notifications": False,
            "dry_run": False,
        }

    def _set_enabled(self, enabled: bool):
        """Enable or disable scheduler."""
        if os.path.exists(self.config_file):
            with open(self.config_file, "r") as f:
                if self.config_file.endswith(".yaml") or self.config_file.endswith(".yml"):
                    import yaml

                    config = yaml.safe_load(f)
                else:
                    import json

                    config = json.load(f)

            config["enabled"] = enabled
            self._save_config(config)

            status = "enabled" if enabled else "disabled"
            emoji = "✅" if enabled else "❌"
            print(f"\n{emoji} Scheduler {status}")

            if self.scheduler:
                self.scheduler.config["enabled"] = enabled
        else:
            print(f"❌ Config file not found: {self.config_file}")

    async def _test_routine(self, routine_type: str):
        """Test a scheduler routine."""
        print(f"\n🧪 Testing {routine_type} routine...")

        if not self.scheduler:
            print("❌ Scheduler not initialized")
            return

        try:
            # Call the correct method based on routine type
            if routine_type == "morning":
                report = self.scheduler.trading_cycle.morning_routine()
            else:
                report = self.scheduler.trading_cycle.evening_routine()

            print(f"\n✅ {routine_type.capitalize()} routine completed")
            print("\nReport preview:")
            print("-" * 70)
            # Show first 500 chars of report
            preview = report[:500] + "..." if len(report) > 500 else report
            print(preview)
            print("-" * 70)
            print("\nFull report saved to: reports/daily/")
        except Exception as e:
            print(f"❌ Test failed: {e}")
            logger.error(f"Routine test error: {e}", exc_info=True)

    def _show_history(self):
        """Show execution history."""
        if not self.scheduler:
            print("❌ Scheduler not initialized")
            return

        print("\n📜 Execution History")
        print("=" * 70)

        history = self.scheduler.get_execution_history(days=7)

        if not history:
            print("No execution history found")
            return

        print("\nShowing last 20 executions (7 days):\n")

        for entry in history[:20]:
            status_emoji = "✅" if entry.status == "completed" else "❌"
            time_str = (
                entry.actual_end_time.strftime("%Y-%m-%d %H:%M")
                if entry.actual_end_time
                else "In Progress"
            )

            print(f"{status_emoji} {entry.task_name:20s} {entry.status:12s} {time_str}")
            if entry.error_message:
                print(f"   ⚠️  {entry.error_message[:60]}...")

    def _show_next_run(self):
        """Calculate and show next scheduled run."""
        if not self.scheduler:
            print("❌ Scheduler not initialized")
            return

        print("\n🔮 Next Scheduled Run")
        print("=" * 70)

        try:
            from datetime import datetime

            import pytz

            et = pytz.timezone("US/Eastern")
            now = datetime.now(et)

            morning_time = dt_time.fromisoformat(self.scheduler.config["morning_routine_time"])
            evening_time = dt_time.fromisoformat(self.scheduler.config["evening_routine_time"])

            morning_today = now.replace(
                hour=morning_time.hour, minute=morning_time.minute, second=0, microsecond=0
            )
            evening_today = now.replace(
                hour=evening_time.hour, minute=evening_time.minute, second=0, microsecond=0
            )

            if now.time() < morning_time:
                next_run = morning_today
                next_task = "Morning Routine"
            elif now.time() < evening_time:
                next_run = evening_today
                next_task = "Evening Routine"
            else:
                from datetime import timedelta

                next_run = morning_today + timedelta(days=1)
                next_task = "Morning Routine (tomorrow)"

            time_until = next_run - now
            hours = int(time_until.total_seconds() // 3600)
            minutes = int((time_until.total_seconds() % 3600) // 60)

            print(f"\n⏰ {next_task}")
            print(f"   Time: {next_run.strftime('%H:%M %p')} ET")
            print(f"   Countdown: {hours}h {minutes}m")
            print(f"   Date: {next_run.strftime('%Y-%m-%d')}")

        except Exception as e:
            print(f"❌ Error calculating next run: {e}")


async def main():
    """Main entry point for standalone scheduler CLI."""
    cli = SchedulerCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
