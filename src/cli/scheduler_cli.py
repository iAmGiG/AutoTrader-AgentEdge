"""
Scheduler CLI - Interactive scheduler management interface.

Provides dedicated commands for:
- Viewing scheduler status with detailed breakdown
- Editing scheduler configuration interactively
- Testing scheduler routines
- Monitoring execution history
- Starting/stopping scheduler service

Messages are loaded from config_defaults/scheduler_cli_messages.yaml
"""

import asyncio
import logging
import os
from datetime import time as dt_time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src.trading.daily_scheduler import DailyScheduler
from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)


def _load_scheduler_messages() -> Dict[str, Any]:
    """Load scheduler CLI messages from YAML configuration."""
    config_path = (
        Path(__file__).parent.parent.parent / "config_defaults" / "scheduler_cli_messages.yaml"
    )

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Could not load scheduler messages from YAML: {e}")
        return {}


# Load messages at module level
MSG = _load_scheduler_messages()


def _get_msg(path: str, default: str = "", **kwargs) -> str:
    """
    Get a message from the config by dot-notation path.

    Args:
        path: Dot-notation path like "welcome.title" or "status.header"
        default: Default value if path not found
        **kwargs: Format arguments for the message

    Returns:
        Formatted message string
    """
    keys = path.split(".")
    value = MSG

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    if isinstance(value, str):
        try:
            return value.format(**kwargs) if kwargs else value
        except KeyError:
            return value

    return str(value) if value else default


def _get_emoji(name: str, default: str = "") -> str:
    """Get an emoji from config."""
    return _get_msg(f"emoji.{name}", default)


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
        """Print scheduler CLI welcome message from config."""
        welcome = MSG.get("welcome", {})

        # Banner and title
        banner = welcome.get("banner", "=" * 70)
        print("\n" + banner)
        print(
            f"   {_get_emoji('calendar', '📅')} {welcome.get('title', 'Scheduler Management CLI')}"
        )
        print(banner)

        # Print each section
        sections = [
            ("quick_start", _get_emoji("rocket", "🚀")),
            ("configuration", _get_emoji("gear", "⚙️")),
            ("testing", _get_emoji("test", "🧪")),
            ("help_section", _get_emoji("book", "📖")),
        ]

        for section_key, emoji in sections:
            section = welcome.get(section_key, {})
            if section:
                header = section.get("header", "")
                print(f"\n{emoji} {header}")
                for cmd in section.get("commands", []):
                    print(f"  {cmd}")

        print("")

    async def _handle_command(self, command: str):
        """
        Handle scheduler CLI commands.

        Args:
            command: User command string
        """
        # Initialize scheduler if needed (except for commands that don't need it)
        no_scheduler_commands = ["help", "config", "edit", "setup", "start", "stop", "logs"]
        if self.scheduler is None and command not in no_scheduler_commands:
            try:
                self.scheduler = DailyScheduler()
            except Exception as e:
                print(f"❌ Failed to initialize scheduler: {e}")
                print("💡 Try running: python main.py --daemon")
                return

        if command == "help":
            self._print_welcome()

        elif command == "setup":
            await self._run_setup_wizard()

        elif command == "start":
            self._start_daemon()

        elif command == "stop":
            self._stop_daemon()

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

        elif command == "logs":
            self._show_logs()

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
        """Display explanations for configuration settings from config."""
        info = MSG.get("config_info", {})
        settings = info.get("settings", {})

        # Header
        print(f"\n{_get_emoji('book', '📖')} {info.get('header', 'Scheduler Configuration Guide')}")
        print("=" * 70)

        # Editable settings section
        print(f"\n🔧 {info.get('editable_header', 'EDITABLE SETTINGS')}")
        print("-" * 70)

        # Map setting names to config keys for current value lookup
        setting_order = ["enabled", "morning_time", "evening_time", "max_retries", "dry_run"]
        config_keys = {
            "enabled": "enabled",
            "morning_time": "morning_routine_time",
            "evening_time": "evening_routine_time",
            "max_retries": "max_retries",
            "dry_run": "dry_run",
        }

        for i, setting_key in enumerate(setting_order, 1):
            setting = settings.get(setting_key, {})
            if not setting:
                continue

            config_key = config_keys.get(setting_key, setting_key)
            current = self.scheduler.config.get(config_key, "N/A") if self.scheduler else "N/A"

            print(f"\n{i}. {setting.get('name', setting_key)}")
            print(f"   Current: {current}")
            print(f"   Purpose: {setting.get('purpose', '')}")

            if "default" in setting:
                print(f"   Default: {setting['default']}")

            for val in setting.get("values", []):
                print(f"   Values:  {val}")

            if "warning" in setting:
                print(f"   {_get_emoji('warning', '⚠️')}  NOTE: {setting['warning']}")

            if "status" in setting:
                print(f"   Status:  {setting['status']}")

            if "tip" in setting:
                print(f"   Tip:     {setting['tip']}")

        # Read-only settings section
        readonly_header = info.get("readonly_header", "READ-ONLY SETTINGS")
        print(f"\n\n{_get_emoji('clipboard', '📋')} {readonly_header}")
        print("-" * 70)

        for setting in info.get("readonly_settings", []):
            print(f"\n• {setting.get('name', '')}: {setting.get('value', '')}")
            print(f"  {setting.get('description', '')}")

        # Quick reference section
        qref = info.get("quick_reference", {})
        print(f"\n\n{_get_emoji('light', '💡')} {qref.get('header', 'QUICK REFERENCE')}")
        print("-" * 70)

        # Paper vs Dry Run
        paper_dry = qref.get("paper_vs_dry", {})
        if paper_dry:
            print(f"\n{paper_dry.get('title', '')}:")
            for item in paper_dry.get("items", []):
                print(f"  • {item}")

        # Safety Levels
        safety = qref.get("safety_levels", {})
        if safety:
            print(f"\n{safety.get('title', '')}:")
            for item in safety.get("items", []):
                print(f"  {item}")

        # Related Issues
        issues = qref.get("related_issues", {})
        if issues:
            print(f"\n{issues.get('title', '')}:")
            for item in issues.get("items", []):
                print(f"  • {item}")

        print("\n" + "=" * 70)
        print(info.get("footer", "Type 'edit' to modify settings or 'config' to view raw file"))
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
            import pytz

            et = pytz.timezone("US/Eastern")
            now = get_datetime_now(et)

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

    async def _run_setup_wizard(self):
        """
        Issue #338: First-time setup wizard for layman users.

        Guides through:
        1. Welcome and explanation
        2. Schedule frequency (twice daily, morning only, evening only)
        3. Time configuration
        4. Save and optionally start
        """
        print("\n" + "=" * 70)
        print("   🧙 Scheduler Setup Wizard")
        print("=" * 70)

        print("\n📖 What does the scheduler do?")
        print("   The scheduler automatically runs trading routines at set times:")
        print("   • Morning routine: Pre-market check, prepare for trading day")
        print("   • Evening routine: End-of-day review, adjust stops")

        print("\n" + "-" * 70)

        # Step 1: Schedule frequency
        print("\n1️⃣  How often should the scheduler run?")
        print("   1. Twice daily (morning + evening) - RECOMMENDED")
        print("   2. Morning only (pre-market)")
        print("   3. Evening only (end-of-day)")
        print("   4. Cancel setup")

        choice = input("\nChoice [1-4]: ").strip()

        if choice == "4":
            print("\n❌ Setup cancelled")
            return

        enable_morning = choice in ["1", "2"]
        enable_evening = choice in ["1", "3"]

        # Step 2: Time configuration
        config = self._get_default_config()

        if enable_morning:
            print("\n2️⃣  Morning routine time (default: 9:20 AM ET, 10 min before market)")
            print("   Press Enter for default, or enter time like '9:00' or '09:30'")
            time_input = input("   Morning time: ").strip()
            if time_input:
                try:
                    # Parse simple time formats
                    if ":" in time_input:
                        parts = time_input.replace("am", "").replace("pm", "").strip().split(":")
                        hour = int(parts[0])
                        minute = int(parts[1]) if len(parts) > 1 else 0
                        config["morning_routine_time"] = f"{hour:02d}:{minute:02d}:00"
                except ValueError:
                    print("   ⚠️  Invalid format, using default 9:20 AM")

        if enable_evening:
            print("\n3️⃣  Evening routine time (default: 3:50 PM ET, 10 min before close)")
            print("   Press Enter for default, or enter time like '15:30' or '3:45'")
            time_input = input("   Evening time: ").strip()
            if time_input:
                try:
                    if ":" in time_input:
                        parts = time_input.replace("pm", "").strip().split(":")
                        hour = int(parts[0])
                        if hour < 12:
                            hour += 12  # Assume PM for evening
                        minute = int(parts[1]) if len(parts) > 1 else 0
                        config["evening_routine_time"] = f"{hour:02d}:{minute:02d}:00"
                except ValueError:
                    print("   ⚠️  Invalid format, using default 3:50 PM")

        # Disable routines if not selected
        if not enable_morning:
            config["morning_routine_enabled"] = False
        if not enable_evening:
            config["evening_routine_enabled"] = False

        config["enabled"] = True

        # Step 3: Summary and save
        print("\n" + "-" * 70)
        print("\n📋 Configuration Summary:")
        print(f"   Morning routine: {'✅ Enabled' if enable_morning else '❌ Disabled'}")
        if enable_morning:
            print(f"      Time: {config.get('morning_routine_time', 'N/A')} ET")
        print(f"   Evening routine: {'✅ Enabled' if enable_evening else '❌ Disabled'}")
        if enable_evening:
            print(f"      Time: {config.get('evening_routine_time', 'N/A')} ET")

        confirm = input("\nSave this configuration? [yes/no]: ").strip().lower()

        if confirm in ["yes", "y"]:
            self._save_config(config)
            print("\n✅ Configuration saved!")

            # Offer to start
            start_now = input("\nStart scheduler now? [yes/no]: ").strip().lower()
            if start_now in ["yes", "y"]:
                self._start_daemon()
        else:
            print("\n❌ Setup cancelled, configuration not saved")

    def _start_daemon(self):
        """
        Issue #338: Start the scheduler daemon.

        Starts the daemon process in the background.
        """
        print("\n🚀 Starting Scheduler Daemon...")

        # Check if already running
        if self._is_daemon_running():
            print("⚠️  Scheduler daemon is already running!")
            print("   Use 'stop' to stop it first, or 'status' to check")
            return

        # Start daemon in background
        import subprocess
        import sys

        try:
            # Get the python executable and main.py path
            python_exe = sys.executable
            main_py = Path(__file__).parent.parent.parent / "main.py"

            if not main_py.exists():
                # Try alternative path
                main_py = Path("main.py")

            # Start in background
            if os.name == "nt":  # Windows
                # Use START /B for background
                subprocess.Popen(
                    [python_exe, str(main_py), "--daemon"],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:  # Unix/Linux/Mac
                subprocess.Popen(
                    [python_exe, str(main_py), "--daemon"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            # Wait a moment and check if it started
            import time

            time.sleep(2)

            if self._is_daemon_running():
                print("✅ Scheduler daemon started successfully!")
                print("   Use 'status' to see details")
                print("   Use 'stop' to stop it later")
            else:
                print("⚠️  Daemon may have started but couldn't verify")
                print("   Check logs with 'logs' command")

        except Exception as e:
            print(f"❌ Failed to start daemon: {e}")
            print("   Try running manually: python main.py --daemon")

    def _stop_daemon(self):
        """
        Issue #338: Stop the scheduler daemon.
        """
        print("\n🛑 Stopping Scheduler Daemon...")

        if not self._is_daemon_running():
            print("ℹ️  Scheduler daemon is not running")
            return

        # Try to stop gracefully
        pid_file = Path("state/scheduler.pid")

        if pid_file.exists():
            try:
                pid = int(pid_file.read_text())

                if os.name == "nt":  # Windows
                    import signal

                    os.kill(pid, signal.SIGTERM)
                else:  # Unix
                    os.kill(pid, 15)  # SIGTERM

                # Wait and verify
                import time

                time.sleep(2)

                if not self._is_daemon_running():
                    print("✅ Scheduler daemon stopped successfully!")
                    # Clean up PID file
                    pid_file.unlink(missing_ok=True)
                else:
                    print("⚠️  Daemon may still be running")
                    print("   Try: kill -9 " + str(pid))

            except (OSError, ValueError) as e:
                print(f"⚠️  Could not stop daemon: {e}")
                print("   You may need to kill the process manually")
        else:
            print("⚠️  PID file not found, daemon may not be managed")
            print("   Check running processes for 'main.py --daemon'")

    def _show_logs(self, lines: int = 50):
        """
        Issue #338: Show recent scheduler logs.
        """
        print("\n📜 Recent Scheduler Logs")
        print("=" * 70)

        # Look for log files
        log_paths = [
            Path("logs/scheduler.log"),
            Path("logs/autotrader.log"),
            Path("state/scheduler_history.json"),
        ]

        log_file = None
        for path in log_paths:
            if path.exists():
                log_file = path
                break

        if not log_file:
            print("ℹ️  No log files found")
            print("   Logs are created when the scheduler runs")
            print("   Try 'test morning' or 'start' first")
            return

        print(f"\nShowing last {lines} lines from: {log_file}\n")
        print("-" * 70)

        try:
            with open(log_file, "r") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines

                for line in recent:
                    # Highlight errors and warnings
                    if "ERROR" in line or "error" in line.lower():
                        print(f"❌ {line.rstrip()}")
                    elif "WARNING" in line or "warn" in line.lower():
                        print(f"⚠️  {line.rstrip()}")
                    elif "SUCCESS" in line or "completed" in line.lower():
                        print(f"✅ {line.rstrip()}")
                    else:
                        print(f"   {line.rstrip()}")

        except Exception as e:
            print(f"❌ Error reading logs: {e}")

        print("-" * 70)
        print(f"\n💡 Full logs at: {log_file}")


async def main():
    """Main entry point for standalone scheduler CLI."""
    cli = SchedulerCLI()
    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
