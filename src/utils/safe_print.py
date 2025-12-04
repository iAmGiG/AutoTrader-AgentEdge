"""
Platform-aware print utilities with emoji fallback support.

Detects platform and terminal capabilities to provide appropriate
emoji/symbol rendering across Windows, Linux, and macOS.
"""

import os
import subprocess
import sys
from typing import Dict

# Platform detection
IS_WINDOWS = sys.platform == "win32"
IS_UNIX = sys.platform in ("linux", "darwin")


# Check if terminal supports UTF-8
def _supports_utf8() -> bool:
    """Check if current terminal supports UTF-8 encoding."""
    try:
        # Check environment variables
        if os.environ.get("PYTHONIOENCODING", "").lower().startswith("utf"):
            return True

        # Check stdout encoding
        if hasattr(sys.stdout, "encoding"):
            encoding = sys.stdout.encoding or ""
            if encoding and "utf" in encoding.lower():  # pylint: disable=no-member
                return True

        # Windows: Check if console is UTF-8 (chcp 65001)
        if IS_WINDOWS:
            try:
                result = subprocess.run(
                    ["chcp"], capture_output=True, text=True, shell=True, check=False  # nosec B602
                )
                return "65001" in result.stdout
            except OSError:
                pass

        return False
    except Exception:  # noqa: E722
        return False


# Emoji configuration with platform-specific fallbacks
EMOJI_CONFIG: Dict[str, Dict[str, str]] = {
    "SUCCESS": {"emoji": "✅", "windows": "[OK]", "ascii": "[+]"},
    "ERROR": {"emoji": "❌", "windows": "[ERROR]", "ascii": "[X]"},
    "INFO": {"emoji": "📊", "windows": "[INFO]", "ascii": "[*]"},
    "CHART": {"emoji": "📈", "windows": "[CHART]", "ascii": "[^]"},
    "WARNING": {"emoji": "⚠️", "windows": "[WARN]", "ascii": "[!]"},
    "ROCKET": {"emoji": "🚀", "windows": ">>>", "ascii": ">>>"},
    "EXPLOSION": {"emoji": "💥", "windows": "[FATAL]", "ascii": "[!!]"},
    "RED": {"emoji": "🔴", "windows": "[HIGH]", "ascii": "[H]"},
    "YELLOW": {"emoji": "🟡", "windows": "[MED]", "ascii": "[M]"},
    "GREEN": {"emoji": "🟢", "windows": "[LOW]", "ascii": "[L]"},
    "EXECUTE": {"emoji": "🔴", "windows": "[EXEC]", "ascii": "[>]"},
    "HOLD": {"emoji": "🟡", "windows": "[HOLD]", "ascii": "[-]"},
    "WAIT": {"emoji": "🟢", "windows": "[WAIT]", "ascii": "[~]"},
    "GEAR": {"emoji": "🔧", "windows": "[CFG]", "ascii": "[=]"},
    "CYCLE": {"emoji": "🔄", "windows": "[SYNC]", "ascii": "[~]"},
    "TARGET": {"emoji": "🎯", "windows": "[TARGET]", "ascii": "[T]"},
    "STOP": {"emoji": "🛑", "windows": "[STOP]", "ascii": "[S]"},
    "BELL": {"emoji": "🔔", "windows": "[ALERT]", "ascii": "[A]"},
    "MAILBOX": {"emoji": "📭", "windows": "[EMPTY]", "ascii": "[ ]"},
    "SLEEP": {"emoji": "💤", "windows": "[IDLE]", "ascii": "[z]"},
    "SAVE": {"emoji": "💾", "windows": "[SAVE]", "ascii": "[S]"},
    "ROBOT": {"emoji": "🤖", "windows": "[BOT]", "ascii": "[AI]"},
}


def get_symbol(symbol_name: str) -> str:
    """
    Get platform-appropriate symbol/emoji.

    Args:
        symbol_name: Name of symbol from EMOJI_CONFIG

    Returns:
        Platform-appropriate symbol string
    """
    config = EMOJI_CONFIG.get(symbol_name.upper())
    if not config:
        return ""

    # Try to use emoji if terminal supports UTF-8
    if _supports_utf8():
        return config["emoji"]

    # Fall back to Windows-friendly or ASCII
    if IS_WINDOWS:
        return config["windows"]

    return config["ascii"]


def safe_print(message: str, **kwargs):
    """
    Print with automatic emoji-to-symbol conversion for platform compatibility.

    Replaces Unicode emojis with platform-appropriate symbols to avoid
    UnicodeEncodeError on Windows terminals.

    Args:
        message: Message to print (may contain emojis)
        **kwargs: Additional arguments passed to print()

    Example:
        safe_print("✅ Task completed successfully")
        # Windows cp1252: "[OK] Task completed successfully"
        # Linux UTF-8: "✅ Task completed successfully"
    """
    # Replace all known emojis with platform-appropriate symbols
    for emoji_key, config in EMOJI_CONFIG.items():
        emoji = config["emoji"]
        if emoji in message:
            replacement = get_symbol(emoji_key)
            message = message.replace(emoji, replacement)

    try:
        print(message, **kwargs)
    except UnicodeEncodeError:
        # Final fallback: remove any remaining non-ASCII characters
        message_ascii = message.encode("ascii", errors="ignore").decode("ascii")
        print(message_ascii, **kwargs)


# Convenience functions for common use cases
def print_success(message: str):
    """Print success message with checkmark."""
    safe_print(f"{get_symbol('SUCCESS')} {message}")


def print_error(message: str):
    """Print error message with X mark."""
    safe_print(f"{get_symbol('ERROR')} {message}")


def print_info(message: str):
    """Print info message with info symbol."""
    safe_print(f"{get_symbol('INFO')} {message}")


def print_warning(message: str):
    """Print warning message with warning symbol."""
    safe_print(f"{get_symbol('WARNING')} {message}")


# Export severity emoji mapper for backward compatibility
def get_severity_symbol(severity: str) -> str:
    """
    Get severity symbol based on level.

    Args:
        severity: 'HIGH', 'MEDIUM', or 'LOW'

    Returns:
        Platform-appropriate severity symbol
    """
    severity_map = {"HIGH": "RED", "MEDIUM": "YELLOW", "LOW": "GREEN"}
    symbol_name = severity_map.get(severity.upper(), "INFO")
    return get_symbol(symbol_name)


if __name__ == "__main__":
    # Test the safe_print functionality
    print("Platform Detection:")
    print(f"  IS_WINDOWS: {IS_WINDOWS}")
    print(f"  IS_UNIX: {IS_UNIX}")
    print(f"  UTF-8 Support: {_supports_utf8()}")
    print(f"  stdout encoding: {sys.stdout.encoding}")
    print()

    print("Symbol Tests:")
    for symbol_name in EMOJI_CONFIG:
        symbol = get_symbol(symbol_name)
        safe_print(f"  {symbol_name}: {symbol}")
    print()

    print("Message Tests:")
    safe_print("✅ Success message")
    safe_print("❌ Error message")
    safe_print("📊 Info message")
    safe_print("⚠️ Warning message")
    safe_print("🚀 Launch message")
    safe_print("💥 Critical error")
    safe_print("🔴🟡🟢 Severity levels")
