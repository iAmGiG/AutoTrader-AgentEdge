"""The CLI's scheduler status sees cron, the recommended way to run the routines."""

import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.cli.scheduler import daemon_manager as daemon_module
from src.cli.scheduler.daemon_manager import SchedulerDaemonManager
from src.cli.scheduler.monitor import SchedulerMonitor

ROOT = "/srv/optionscommander"
ENTRY = f"*/5 * * * * cd {ROOT} && /usr/bin/python main.py --run-due > /dev/null"


def _manager(monkeypatch, crontab="", returncode=0, error=None):
    def run(*args, **kwargs):
        if error:
            raise error
        return SimpleNamespace(returncode=returncode, stdout=crontab)

    monkeypatch.setattr(daemon_module.subprocess, "run", run)
    return SchedulerDaemonManager(main_script=Path(ROOT) / "main.py")


def test_the_run_due_entry_for_this_checkout_is_found(monkeypatch):
    crontab = f"0 1 * * * /opt/gex/collect.sh\n{ENTRY}\n"

    assert _manager(monkeypatch, crontab).cron_entry() == ENTRY


@pytest.mark.parametrize(
    "crontab",
    [
        f"# {ENTRY}\n",  # commented out
        ENTRY.replace(ROOT, "/home/other/checkout") + "\n",  # another checkout
        f"*/5 * * * * cd {ROOT} && python main.py --daemon\n",  # not the cron entry point
        "",
    ],
)
def test_other_lines_are_not_this_checkouts_entry(monkeypatch, crontab):
    assert _manager(monkeypatch, crontab).cron_entry() is None


def test_no_crontab_or_no_crontab_command_means_no_entry(monkeypatch):
    assert _manager(monkeypatch, returncode=1).cron_entry() is None
    assert _manager(monkeypatch, error=FileNotFoundError("crontab")).cron_entry() is None
    assert _manager(monkeypatch, error=subprocess.TimeoutExpired("crontab", 5)).cron_entry() is None


def _status(capsys, daemon=False, cron=None, enabled=True):
    scheduler = MagicMock()
    scheduler.effective_settings.return_value = {"enabled": enabled}
    scheduler.config = {}
    scheduler.get_execution_history.return_value = []
    monitor = SchedulerMonitor(scheduler)
    monitor.daemon_manager = MagicMock()
    monitor.daemon_manager.is_running.return_value = daemon
    monitor.daemon_manager.cron_entry.return_value = cron
    monitor.show_status()
    return capsys.readouterr().out


def test_status_reports_cron_as_running(capsys):
    out = _status(capsys, cron=ENTRY)

    assert "Service: CRON" in out
    assert "NOT RUNNING" not in out
    assert "no automatic executions" not in out


def test_status_says_cron_runs_nothing_while_disabled(capsys):
    assert "disabled, so cron runs no routines" in _status(capsys, cron=ENTRY, enabled=False)


def test_without_cron_or_daemon_status_suggests_the_cron_setup(capsys):
    out = _status(capsys)

    assert "NOT RUNNING" in out
    assert "setup_cron.sh" in out
