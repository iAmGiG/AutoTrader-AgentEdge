"""CLI tools are Microsoft Agent Framework FunctionTools (#606 step 2), not AutoGen's."""

import json
import subprocess
import sys
from pathlib import Path

from agent_framework import FunctionTool

import src.cli.tools as cli_tools

REPO = Path(__file__).resolve().parents[3]


def test_every_registered_tool_is_an_agent_framework_tool_with_a_schema():
    tools = cli_tools.get_all_cli_tools()

    assert len(tools) >= 100
    for tool in tools:
        assert isinstance(tool, FunctionTool), tool
        assert tool.name and tool.description, tool.name
        assert callable(tool.func), tool.name
        json.dumps(tool.parameters())  # the JSON schema an agent is given


def test_tool_names_are_unique():
    names = [tool.name for tool in cli_tools.get_all_cli_tools()]

    assert len(names) == len(set(names))


def test_the_cli_tools_load_no_autogen():
    code = (
        "import sys, src.cli.tools; "
        "print(sorted({m.split('.')[0] for m in sys.modules if m.startswith('autogen')}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=REPO
    )

    assert out.stdout.strip() == "[]"
