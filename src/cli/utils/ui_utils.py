"""
UI utilities for CLI platform-aware rendering.

Issue #521: Consolidate platform-aware UI rendering patterns.
"""

import subprocess

from config_defaults.message_loader import CLIMessages as MSG  # noqa: N814

from src.utils.safe_print import IS_WINDOWS, get_symbol


def get_error_prefix() -> str:
    """
    Get platform-appropriate error prefix.

    Returns:
        Error symbol suitable for the current platform
    """
    return get_symbol("ERROR")


def get_mode_indicator(autonomy_mode: str) -> str:
    """
    Get mode indicator with platform-appropriate formatting.

    Uses ASCII on Windows to avoid encoding issues, includes emoji on other platforms.

    Args:
        autonomy_mode: Either "auto" or "confirm"

    Returns:
        Platform-appropriate mode indicator string
    """
    if autonomy_mode == "auto":
        return f"{MSG.EMOJI['auto_mode']} AUTO"
    else:
        return f"{MSG.EMOJI['confirm_mode']} CONFIRM"


def clear_screen() -> None:
    """
    Clear terminal screen using platform-appropriate command.

    Uses 'cls' on Windows, 'clear' on Unix-like systems.
    """
    command = "cls" if IS_WINDOWS else "clear"
    subprocess.run(command, shell=False, check=False)
