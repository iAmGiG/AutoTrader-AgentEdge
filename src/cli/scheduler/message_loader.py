"""
Scheduler message loader - loads CLI messages from YAML configuration.

Reusable utility for loading messages from config files with dot-notation access.
Extracted from scheduler_cli.py (Issue #440).
"""

import logging
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)


class SchedulerMessageLoader:
    """
    Load and access CLI messages from YAML configuration.

    Provides dot-notation access to hierarchical message structures
    and caches loaded messages for performance.
    """

    def __init__(self, config_path: Path = None):
        """
        Initialize message loader.

        Args:
            config_path: Path to YAML config file. Defaults to scheduler_cli_messages.yaml
        """
        if config_path is None:
            config_path = (
                Path(__file__).parent.parent.parent.parent
                / "config_defaults"
                / "scheduler_cli_messages.yaml"
            )
        self._config_path = config_path
        self._messages: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load messages from YAML file."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._messages = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load scheduler messages from YAML: {e}")
            self._messages = {}

    def get(self, path: str, default: str = "", **kwargs) -> str:
        """
        Get a message by dot-notation path.

        Args:
            path: Dot-notation path like "welcome.title" or "status.header"
            default: Default value if path not found
            **kwargs: Format arguments for the message

        Returns:
            Formatted message string
        """
        keys = path.split(".")
        value = self._messages

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        if isinstance(value, str):
            try:
                return value.format(**kwargs) if kwargs else value
            except KeyError:
                return value

        return str(value) if value else default

    def get_emoji(self, name: str, default: str = "") -> str:
        """
        Get an emoji by name from the emoji section.

        Args:
            name: Emoji name (e.g., "check_green", "cross_red")
            default: Default emoji if not found

        Returns:
            Emoji string
        """
        return self.get(f"emoji.{name}", default)

    def get_dict(self, path: str = "") -> Dict[str, Any]:
        """
        Get a dictionary section from messages.

        Args:
            path: Optional dot-notation path to nested dict

        Returns:
            Dictionary of messages
        """
        if not path:
            return self._messages

        keys = path.split(".")
        value = self._messages

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return {}

        return value if isinstance(value, dict) else {}

    def reload(self) -> None:
        """Reload messages from file."""
        self._load()


# Module-level singleton and convenience functions
_loader: SchedulerMessageLoader = None


def _get_loader() -> SchedulerMessageLoader:
    """Get or create the module-level loader singleton."""
    global _loader
    if _loader is None:
        _loader = SchedulerMessageLoader()
    return _loader


def get_msg(path: str, default: str = "", **kwargs) -> str:
    """
    Get a message by dot-notation path.

    Convenience function using module-level loader.
    """
    return _get_loader().get(path, default, **kwargs)


def get_emoji(name: str, default: str = "") -> str:
    """
    Get an emoji by name.

    Convenience function using module-level loader.
    """
    return _get_loader().get_emoji(name, default)


def get_messages() -> Dict[str, Any]:
    """Get all messages dictionary."""
    return _get_loader().get_dict()
