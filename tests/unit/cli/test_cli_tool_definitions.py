"""CLI tools are Microsoft Agent Framework FunctionTools (#606 step 2), not AutoGen's."""

import json
import os
import subprocess
import sys
from pathlib import Path

from agent_framework import FunctionTool

import src.cli.tools as cli_tools

REPO = Path(__file__).resolve().parents[3]

# Every category the registry loads a module for (src/cli/tools/__init__.py)
CATEGORIES = [
    value
    for name, value in vars(cli_tools).items()
    if name.endswith("_TOOLS") and name != "REQUIRES_APPROVAL" and isinstance(value, str)
]


def test_every_tool_module_loaded():
    """The loader only logs a module that fails to import, so check each category."""
    assert len(CATEGORIES) >= 15
    for category in CATEGORIES:
        assert cli_tools.get_cli_tools_by_category(category), f"no tools loaded for {category}"


def test_every_registered_tool_is_an_agent_framework_tool_with_a_schema():
    for tool in cli_tools.get_all_cli_tools():
        assert isinstance(tool, FunctionTool), tool
        assert tool.name and tool.description, tool.name
        assert callable(tool.func), tool.name
        json.dumps(tool.parameters())  # the JSON schema an agent is given


def test_tool_names_are_unique():
    names = [tool.name for tool in cli_tools.get_all_cli_tools()]

    assert len(names) == len(set(names))


def test_tools_that_change_orders_modes_or_data_need_approval():
    tools = {tool.name: tool for tool in cli_tools.get_all_cli_tools()}

    assert cli_tools.REQUIRES_APPROVAL <= set(tools)  # every name is a real tool
    for name, tool in tools.items():
        expected = "always_require" if name in cli_tools.REQUIRES_APPROVAL else "never_require"
        assert tool.approval_mode == expected, name


def test_the_cli_tools_load_no_autogen(tmp_path):
    """Run from a temp dir: importing src.trading creates .cache/ in the working dir (#600)."""
    code = (
        "import sys, src.cli.tools; "
        "print('AUTOGEN=' + ','.join(sorted({m.split('.')[0] for m in sys.modules "
        "if m.startswith('autogen')})))"
    )
    env = {**os.environ, "PYTHONPATH": str(REPO), "AUTOTRADER_STATE_DIR": str(tmp_path)}
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
        env=env,
    )

    marker = [line for line in out.stdout.splitlines() if line.startswith("AUTOGEN=")]
    assert marker == ["AUTOGEN="]
