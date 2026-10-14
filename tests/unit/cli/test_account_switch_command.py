"""
The typed "switch to account <ID>" command is how the user reaches a live account, so
it must parse the ID and pass the confirmation prompt (agent tools never do).
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from src.cli.cli_session import CLISession
from src.cli.commands.account_commands import confirm_live_switch


@pytest.mark.parametrize(
    "typed", ["switch to account paper_main", "switch account paper_main", "use account paper_main"]
)
def test_typed_switch_passes_id_and_confirmation_prompt(typed):
    session = CLISession.__new__(CLISession)  # only the account handler is exercised
    session.account_commands = MagicMock()
    session.account_commands.switch_account.return_value = {"status": "error"}

    asyncio.run(session._handle_account_request(typed))

    session.account_commands.switch_account.assert_called_once_with(
        "paper_main", confirm_live=confirm_live_switch
    )


def test_live_confirmation_requires_the_exact_account_id(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    assert not confirm_live_switch("live_main")

    monkeypatch.setattr("builtins.input", lambda prompt: " live_main ")
    assert confirm_live_switch("live_main")
