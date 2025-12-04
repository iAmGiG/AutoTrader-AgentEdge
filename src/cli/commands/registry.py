"""
CLI Command Registry - Self-registering command pattern.

Issue #468: Refactor from if/elif chain to decorator-based registration.

Usage:
    @command("/about", help_text="Status dashboard")
    async def cmd_about(session):
        display_about(session.account_monitor)

    # In cli_session.py:
    result = await CommandRegistry.execute(command, session)
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CommandRegistry:
    """
    Registry for CLI slash commands.

    Commands self-register using the @command decorator.
    Supports aliases and auto-generated help text.
    """

    _commands: Dict[str, Dict[str, Any]] = {}
    _aliases: Dict[str, str] = {}  # alias -> primary command

    @classmethod
    def register(
        cls,
        name: str,
        aliases: Optional[List[str]] = None,
        help_text: str = "",
        has_args: bool = False,
    ) -> Callable:
        """
        Decorator to register a command.

        Args:
            name: Command name (e.g., "/about")
            aliases: Alternative names (e.g., ["/info"])
            help_text: Description for /help output
            has_args: True if command accepts arguments

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            cls._commands[name] = {
                "handler": func,
                "aliases": aliases or [],
                "help": help_text,
                "has_args": has_args,
            }
            # Register aliases
            for alias in aliases or []:
                cls._aliases[alias] = name
            logger.debug(f"Registered command: {name}")
            return func

        return decorator

    @classmethod
    def get(cls, cmd: str) -> Optional[Dict[str, Any]]:
        """
        Get command info by name or alias.

        Args:
            cmd: Command string (e.g., "/about" or "/faq features")

        Returns:
            Command dict or None if not found
        """
        # Extract base command (before any arguments)
        parts = cmd.split(None, 1)
        base_cmd = parts[0].lower()

        # Check direct match
        if base_cmd in cls._commands:
            return cls._commands[base_cmd]

        # Check aliases
        if base_cmd in cls._aliases:
            primary = cls._aliases[base_cmd]
            return cls._commands.get(primary)

        # Check for commands that accept arguments
        for name, info in cls._commands.items():
            if info.get("has_args") and cmd.lower().startswith(name):
                return info

        return None

    @classmethod
    async def execute(cls, cmd: str, session: Any) -> Tuple[bool, bool]:
        """
        Execute a command.

        Args:
            cmd: Full command string (e.g., "/faq features")
            session: CLISession instance

        Returns:
            Tuple of (handled: bool, should_continue: bool)
            - handled: True if command was found and executed
            - should_continue: True to continue session, False to exit
        """
        command_info = cls.get(cmd)

        if not command_info:
            return False, True  # Not handled, continue

        handler = command_info["handler"]

        # Extract arguments if command has them
        parts = cmd.split(None, 1)
        args = parts[1] if len(parts) > 1 else None

        try:
            # Call handler - may be sync or async
            if command_info.get("has_args"):
                result = handler(session, args)
            else:
                result = handler(session)

            # Handle async handlers
            if hasattr(result, "__await__"):
                result = await result

            # Result of False means exit
            should_continue = result is not False

            return True, should_continue

        except Exception as e:
            logger.exception(f"Error executing command {cmd}: {e}")
            return True, True  # Handled (with error), continue

    @classmethod
    def get_help(cls) -> str:
        """
        Generate help text from registered commands.

        Returns:
            Formatted help string
        """
        lines = ["Commands:"]

        # Sort commands alphabetically
        for name in sorted(cls._commands.keys()):
            info = cls._commands[name]
            help_text = info.get("help", "")
            # Format: /command  - description
            lines.append(f"  {name:10} - {help_text}")

        return "\n".join(lines)

    @classmethod
    def list_commands(cls) -> List[str]:
        """Get list of registered command names."""
        return list(cls._commands.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered commands (for testing)."""
        cls._commands.clear()
        cls._aliases.clear()


# Convenience decorator
def command(
    name: str,
    aliases: Optional[List[str]] = None,
    help_text: str = "",
    has_args: bool = False,
) -> Callable:
    """
    Decorator to register a CLI command.

    Usage:
        @command("/about", help_text="Status dashboard")
        def cmd_about(session):
            ...
    """
    return CommandRegistry.register(name, aliases, help_text, has_args)
