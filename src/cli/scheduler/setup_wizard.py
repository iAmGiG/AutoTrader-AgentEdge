"""
Scheduler setup wizard - first-time setup flow for layman users.

Guides users through initial scheduler configuration.
Extracted from scheduler_cli.py (Issue #440, implements #338).
"""

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from .config_editor import SchedulerConfigEditor
from .daemon_manager import SchedulerDaemonManager
from .message_loader import get_emoji

if TYPE_CHECKING:
    from src.trading.daily_scheduler import DailyScheduler

logger = logging.getLogger(__name__)


class SchedulerSetupWizard:
    """
    First-time setup wizard for scheduler configuration.

    Guides users through:
    1. Welcome and explanation
    2. Schedule frequency selection
    3. Time configuration
    4. Save and optionally start daemon
    """

    def __init__(self, scheduler: Optional["DailyScheduler"] = None):
        """
        Initialize setup wizard.

        Args:
            scheduler: Optional existing scheduler instance
        """
        self.scheduler = scheduler
        self.config_editor = SchedulerConfigEditor()
        self.daemon_manager = SchedulerDaemonManager()

    async def run(self) -> Optional[Dict[str, Any]]:  # noqa: C901
        """
        Run the setup wizard.

        Returns:
            Configuration dict if completed, None if cancelled
        """
        print("\n" + "=" * 70)
        print(f"   {get_emoji('wizard', '🧙')} Scheduler Setup Wizard")
        print("=" * 70)

        # Explanation
        print(f"\n{get_emoji('book', '📖')} What does the scheduler do?")
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
            print(f"\n{get_emoji('cross_red', '❌')} Setup cancelled")
            return None

        enable_morning = choice in ["1", "2"]
        enable_evening = choice in ["1", "3"]

        # Step 2: Time configuration
        config = SchedulerConfigEditor.DEFAULT_CONFIG.copy()

        if enable_morning:
            print("\n2️⃣  Morning routine time (default: 9:20 AM ET, 10 min before market)")
            print("   Press Enter for default, or enter time like '9:00' or '09:30'")
            time_input = input("   Morning time: ").strip()

            if time_input:
                normalized = self._parse_time(time_input)
                if normalized:
                    config["morning_routine_time"] = normalized
                else:
                    print(f"   {get_emoji('warning', '⚠️')} Invalid format, using default 9:20 AM")

        if enable_evening:
            print("\n3️⃣  Evening routine time (default: 3:50 PM ET, 10 min before close)")
            print("   Press Enter for default, or enter time like '15:30' or '3:45'")
            time_input = input("   Evening time: ").strip()

            if time_input:
                normalized = self._parse_time(time_input, assume_pm=True)
                if normalized:
                    config["evening_routine_time"] = normalized
                else:
                    print(f"   {get_emoji('warning', '⚠️')} Invalid format, using default 3:50 PM")

        # Disable routines if not selected
        if not enable_morning:
            config["morning_routine_enabled"] = False
        if not enable_evening:
            config["evening_routine_enabled"] = False

        config["enabled"] = True

        # Step 3: Summary and save
        print("\n" + "-" * 70)
        print(f"\n{get_emoji('clipboard', '📋')} Configuration Summary:")

        morning_status = (
            f"{get_emoji('check_green', '✅')} Enabled"
            if enable_morning
            else f"{get_emoji('cross_red', '❌')} Disabled"
        )
        evening_status = (
            f"{get_emoji('check_green', '✅')} Enabled"
            if enable_evening
            else f"{get_emoji('cross_red', '❌')} Disabled"
        )

        print(f"   Morning routine: {morning_status}")
        if enable_morning:
            print(f"      Time: {config.get('morning_routine_time', 'N/A')} ET")

        print(f"   Evening routine: {evening_status}")
        if enable_evening:
            print(f"      Time: {config.get('evening_routine_time', 'N/A')} ET")

        confirm = input("\nSave this configuration? [yes/no]: ").strip().lower()

        if confirm in ["yes", "y"]:
            if self.config_editor.save(config):
                print(f"\n{get_emoji('check_green', '✅')} Configuration saved!")

                # Offer to start daemon
                start_now = input("\nStart scheduler now? [yes/no]: ").strip().lower()
                if start_now in ["yes", "y"]:
                    self.daemon_manager.start()

                return config
            else:
                print(f"\n{get_emoji('cross_red', '❌')} Failed to save configuration")
                return None
        else:
            print(f"\n{get_emoji('cross_red', '❌')} Setup cancelled, configuration not saved")
            return None

    def _parse_time(self, time_input: str, assume_pm: bool = False) -> Optional[str]:
        """
        Parse user time input to HH:MM:SS format.

        Args:
            time_input: User input like "9:00", "9:30", "15:30"
            assume_pm: If True, assume PM for hour < 12

        Returns:
            Normalized time string or None if invalid
        """
        try:
            # Clean input
            time_input = time_input.replace("am", "").replace("pm", "").strip()

            if ":" not in time_input:
                return None

            parts = time_input.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0

            # Assume PM for evening times
            if assume_pm and hour < 12:
                hour += 12

            # Validate
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None

            return f"{hour:02d}:{minute:02d}:00"

        except (ValueError, IndexError):
            return None
