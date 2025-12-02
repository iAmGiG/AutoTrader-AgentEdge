"""
Scheduler daemon manager - cross-platform process management.

Handles starting, stopping, and monitoring the scheduler daemon process.
Extracted from scheduler_cli.py (Issue #440).
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from .message_loader import get_emoji

logger = logging.getLogger(__name__)


class SchedulerDaemonManager:
    """
    Cross-platform daemon lifecycle management.

    Handles:
    - Starting daemon in background
    - Stopping daemon gracefully
    - Checking daemon status
    - PID file management
    """

    def __init__(self, pid_file: Path = None, main_script: Path = None):
        """
        Initialize daemon manager.

        Args:
            pid_file: Path to PID file. Defaults to state/scheduler.pid
            main_script: Path to main.py. Auto-detected if not provided.
        """
        self.pid_file = pid_file or Path("state/scheduler.pid")
        self.main_script = main_script or self._find_main_script()

    def _find_main_script(self) -> Path:
        """Find main.py script path."""
        # Try relative to this file first
        main_py = Path(__file__).parent.parent.parent.parent / "main.py"
        if main_py.exists():
            return main_py

        # Try current directory
        main_py = Path("main.py")
        if main_py.exists():
            return main_py

        return Path("main.py")  # Default, may not exist

    def is_running(self) -> bool:
        """
        Check if scheduler daemon is running.

        Uses psutil if available, falls back to PID file check.

        Returns:
            True if daemon is running
        """
        # Try psutil first (more reliable)
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info.get("cmdline", [])
                    if cmdline and "main.py" in " ".join(cmdline) and "--daemon" in cmdline:
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"psutil check failed: {e}")

        # Fallback: Check PID file
        if self.pid_file.exists():
            try:
                pid = int(self.pid_file.read_text().strip())
                os.kill(pid, 0)  # Signal 0 = check if process exists
                return True
            except (OSError, ValueError):
                pass

        return False

    def get_pid(self) -> Optional[int]:
        """
        Get the daemon PID if running.

        Returns:
            PID or None if not running
        """
        if not self.pid_file.exists():
            return None

        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)  # Verify process exists
            return pid
        except (OSError, ValueError):
            return None

    def start(self) -> bool:
        """
        Start the scheduler daemon in background.

        Returns:
            True if started successfully
        """
        print(f"\n{get_emoji('rocket', '🚀')} Starting Scheduler Daemon...")

        if self.is_running():
            print(f"{get_emoji('warning', '⚠️')} Scheduler daemon is already running!")
            print("   Use 'stop' to stop it first, or 'status' to check")
            return False

        if not self.main_script.exists():
            print(f"{get_emoji('cross_red', '❌')} main.py not found at: {self.main_script}")
            return False

        try:
            python_exe = sys.executable

            if os.name == "nt":  # Windows
                subprocess.Popen(
                    [python_exe, str(self.main_script), "--daemon"],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:  # Unix/Linux/Mac
                subprocess.Popen(
                    [python_exe, str(self.main_script), "--daemon"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            # Wait and verify
            time.sleep(2)

            if self.is_running():
                print(f"{get_emoji('check_green', '✅')} Scheduler daemon started successfully!")
                print("   Use 'status' to see details")
                print("   Use 'stop' to stop it later")
                return True
            else:
                print(f"{get_emoji('warning', '⚠️')} Daemon may have started but couldn't verify")
                print("   Check logs with 'logs' command")
                return False

        except Exception as e:
            print(f"{get_emoji('cross_red', '❌')} Failed to start daemon: {e}")
            print("   Try running manually: python main.py --daemon")
            logger.error(f"Failed to start daemon: {e}", exc_info=True)
            return False

    def stop(self) -> bool:  # noqa: C901
        """
        Stop the scheduler daemon gracefully.

        Returns:
            True if stopped successfully
        """
        print(f"\n{get_emoji('stop', '🛑')} Stopping Scheduler Daemon...")

        if not self.is_running():
            print(f"{get_emoji('info', 'ℹ️')} Scheduler daemon is not running")
            return True

        pid = self.get_pid()
        if pid is None:
            # Try to find via psutil
            try:
                import psutil

                for proc in psutil.process_iter(["pid", "cmdline"]):
                    try:
                        cmdline = proc.info.get("cmdline", [])
                        if cmdline and "main.py" in " ".join(cmdline) and "--daemon" in cmdline:
                            pid = proc.info["pid"]
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except ImportError:
                pass

        if pid is None:
            print(f"{get_emoji('warning', '⚠️')} Could not find daemon PID")
            print("   Check running processes for 'main.py --daemon'")
            return False

        try:
            if os.name == "nt":  # Windows
                import signal

                os.kill(pid, signal.SIGTERM)
            else:  # Unix
                os.kill(pid, 15)  # SIGTERM

            # Wait and verify
            time.sleep(2)

            if not self.is_running():
                print(f"{get_emoji('check_green', '✅')} Scheduler daemon stopped successfully!")
                # Clean up PID file
                if self.pid_file.exists():
                    self.pid_file.unlink(missing_ok=True)
                return True
            else:
                print(f"{get_emoji('warning', '⚠️')} Daemon may still be running")
                print(f"   Try: kill -9 {pid}")
                return False

        except OSError as e:
            print(f"{get_emoji('warning', '⚠️')} Could not stop daemon: {e}")
            print("   You may need to kill the process manually")
            return False

    def restart(self) -> bool:
        """
        Restart the scheduler daemon.

        Returns:
            True if restarted successfully
        """
        print(f"\n{get_emoji('refresh', '🔄')} Restarting Scheduler Daemon...")
        self.stop()
        time.sleep(1)
        return self.start()
