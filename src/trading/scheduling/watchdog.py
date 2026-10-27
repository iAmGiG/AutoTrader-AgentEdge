"""
Wall-clock limit for one cron check (`main.py --run-due`).

Cron starts a check every 5 minutes and the run lock keeps them from overlapping, so a
check that hangs (a broker call that never answers, a stuck database) blocks every later
one until someone notices. The limit ends such a check: SIGALRM raises RunDueTimeoutError
in the main thread, the routine in progress is recorded as failed, and the process exits.

The error derives from BaseException on purpose: the retry loop and the routine's
contained steps catch Exception, and a timeout must be neither retried nor swallowed.
"""

import logging
import signal
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

# Retries included: a routine takes under ten minutes with the default retries
RUN_DUE_TIMEOUT_SECONDS = 900

CONFIG_KEY = "run_due_timeout_seconds"


class RunDueTimeoutError(BaseException):
    """The cron check ran past its wall-clock limit."""

    def __init__(self, limit_seconds: int):
        super().__init__(f"timed out after {limit_seconds} s")
        self.limit_seconds = limit_seconds
        self.log_entry: Any = None  # the routine's ExecutionLog, when it was running
        self.routine_recorded = False  # set once its failure was recorded and noticed


def run_due_timeout_seconds(config: Optional[Dict[str, Any]] = None) -> int:
    """The limit: the scheduler config's run_due_timeout_seconds, else the default."""
    value = (config or {}).get(CONFIG_KEY)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        if value is not None:
            logger.warning("Ignoring %s=%r; using %d", CONFIG_KEY, value, RUN_DUE_TIMEOUT_SECONDS)
        return RUN_DUE_TIMEOUT_SECONDS
    return max(1, int(value))


@contextmanager
def watchdog(limit_seconds: int) -> Iterator[bool]:
    """
    Raise RunDueTimeoutError in the main thread once the block has run limit_seconds.
    The alarm is disarmed and the previous handler restored on the way out. Without
    SIGALRM (Windows) or outside the main thread there is no limit: yields False.
    """
    if not hasattr(signal, "SIGALRM"):
        yield False
        return

    def on_alarm(signum, frame):
        raise RunDueTimeoutError(limit_seconds)

    try:
        previous = signal.signal(signal.SIGALRM, on_alarm)
    except ValueError:  # not the main thread
        yield False
        return
    signal.alarm(limit_seconds)
    try:
        yield True
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)
