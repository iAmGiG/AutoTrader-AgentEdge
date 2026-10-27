"""
The cron entry (`main.py --run-due`) imports everything it needs, and importing it creates
no files: an import error there would stop every scheduled routine.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_main_imports_cleanly_and_creates_nothing(tmp_path):
    work = tmp_path / "cwd"
    work.mkdir()
    env = dict(os.environ)
    env.pop("RUN_PAPER_ORDER_TESTS", None)
    env.update(
        AUTOTRADER_STATE_DIR=str(tmp_path / "state"),
        AUTOTRADER_CACHE_DIR=str(tmp_path / "cache"),
        PYTHONPATH=str(REPO),
        PYTHONDONTWRITEBYTECODE="1",
    )

    result = subprocess.run(
        [sys.executable, "-c", "import main; print('CLI_AVAILABLE', main.CLI_AVAILABLE)"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr[-2000:]
    assert "CLI_AVAILABLE True" in result.stdout.splitlines()
    assert sorted(tmp_path.rglob("*")) == [work]  # no state, cache or other files
