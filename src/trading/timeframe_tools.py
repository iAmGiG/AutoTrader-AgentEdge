"""
Timeframe Management Tools for Agents and CLI (Issue #365)

Provides agent-compatible tools for changing, querying, and validating trading timeframes.
Designed for use with AutoGen agents and CLI natural language commands.
"""

from typing import Dict, List, Optional

from config_defaults.trading_config import get_config


class TimeframeManager:
    """Manages timeframe configuration and validation."""

    def __init__(self):
        """Initialize timeframe manager."""
        self.config = get_config()
        self.current_timeframe = self._get_current_timeframe()

    def _get_current_timeframe(self) -> str:
        """Get current active timeframe."""
        timeframe_config = self.config.get_timeframe_config()
        return timeframe_config.default

    def get_current_timeframe(self) -> str:
        """Get the currently active timeframe."""
        return self.current_timeframe

    def set_timeframe(self, timeframe: str) -> Dict[str, any]:
        """
        Set the active timeframe.

        Args:
            timeframe: Timeframe to activate (e.g., "1d", "1h", "5m")

        Returns:
            Dictionary with success status and message
        """
        timeframe_config = self.config.get_timeframe_config()

        if not timeframe_config.is_valid(timeframe):
            return {
                "success": False,
                "message": f"Invalid timeframe '{timeframe}'. Valid options: {', '.join(timeframe_config.enabled_timeframes)}",
                "current_timeframe": self.current_timeframe,
            }

        self.current_timeframe = timeframe
        return {
            "success": True,
            "message": f"Timeframe changed to {timeframe}",
            "current_timeframe": self.current_timeframe,
        }

    def get_available_timeframes(self) -> Dict[str, List[str]]:
        """Get all available timeframes grouped by trading style."""
        timeframe_config = self.config.get_timeframe_config()

        return {
            "scalping": ["1m", "5m"],
            "day_trading": ["15m", "30m"],
            "swing_trading": ["1h", "2h", "4h"],
            "position_trading": ["1d"],
            "intermediate_term": ["1w"],
            "long_term": ["1M"],
            "all_enabled": timeframe_config.enabled_timeframes,
        }

    def validate_timeframe(self, timeframe: str) -> Dict[str, any]:
        """
        Validate a timeframe string.

        Args:
            timeframe: Timeframe to validate

        Returns:
            Dictionary with validation results
        """
        timeframe_config = self.config.get_timeframe_config()
        is_valid = timeframe_config.is_valid(timeframe)

        return {
            "timeframe": timeframe,
            "valid": is_valid,
            "message": "Valid timeframe" if is_valid else f"Invalid timeframe '{timeframe}'",
            "available": timeframe_config.enabled_timeframes,
        }

    def get_timeframe_info(self, timeframe: str) -> Dict[str, any]:
        """
        Get information about a specific timeframe.

        Args:
            timeframe: Timeframe to get info for

        Returns:
            Dictionary with timeframe information
        """
        timeframe_descriptions = {
            "1m": "1 minute - scalping/EA signals, micro trends",
            "5m": "5 minutes - fast intraday trading, quick reactions",
            "15m": "15 minutes - standard intraday, trend following",
            "30m": "30 minutes - intraday swing trading, medium trends",
            "1h": "1 hour - medium-term trading, strong support/resistance",
            "2h": "2 hours - medium-term swing, consolidation patterns",
            "4h": "4 hours - swing/position trading, strong for crypto",
            "1d": "1 day - VALIDATED DEFAULT, best Sharpe (0.856), position trading",
            "1w": "1 week - intermediate-term, major trends",
            "1M": "1 month - long-term positioning, institutional moves",
        }

        if not self.validate_timeframe(timeframe)["valid"]:
            return {"success": False, "message": f"Invalid timeframe: {timeframe}"}

        return {
            "timeframe": timeframe,
            "description": timeframe_descriptions.get(timeframe, "Unknown timeframe"),
            "current": timeframe == self.current_timeframe,
        }

    def list_timeframes(self, verbose: bool = False) -> Dict[str, any]:
        """
        List all available timeframes.

        Args:
            verbose: Include descriptions if True

        Returns:
            Dictionary with timeframe list
        """
        timeframe_config = self.config.get_timeframe_config()
        timeframes = timeframe_config.enabled_timeframes

        if verbose:
            return {
                "timeframes": [
                    {
                        "tf": tf,
                        "current": tf == self.current_timeframe,
                        "info": self.get_timeframe_info(tf).get("description", ""),
                    }
                    for tf in timeframes
                ],
                "current": self.current_timeframe,
            }
        else:
            return {
                "timeframes": timeframes,
                "current": self.current_timeframe,
            }


# ============================================================================
# AGENT TOOLS (AutoGen-compatible)
# ============================================================================

_timeframe_manager = None


def _get_timeframe_manager() -> TimeframeManager:
    """Get global timeframe manager instance."""
    global _timeframe_manager
    if _timeframe_manager is None:
        _timeframe_manager = TimeframeManager()
    return _timeframe_manager


def get_current_timeframe() -> Dict[str, any]:
    """
    Get the current active timeframe.

    Returns:
        Dictionary with current timeframe
    """
    manager = _get_timeframe_manager()
    return {"current_timeframe": manager.get_current_timeframe()}


def set_current_timeframe(timeframe: str) -> Dict[str, any]:
    """
    Change the active trading timeframe.

    Args:
        timeframe: New timeframe (e.g., "1h", "4h", "1d")

    Returns:
        Dictionary with status and current timeframe
    """
    manager = _get_timeframe_manager()
    return manager.set_timeframe(timeframe)


def list_available_timeframes(include_descriptions: bool = False) -> Dict[str, any]:
    """
    List all available timeframes.

    Args:
        include_descriptions: Include timeframe descriptions if True

    Returns:
        Dictionary with available timeframes
    """
    manager = _get_timeframe_manager()
    return manager.list_timeframes(verbose=include_descriptions)


def validate_timeframe(timeframe: str) -> Dict[str, any]:
    """
    Check if a timeframe is valid.

    Args:
        timeframe: Timeframe to validate

    Returns:
        Dictionary with validation results
    """
    manager = _get_timeframe_manager()
    return manager.validate_timeframe(timeframe)


def get_timeframe_recommendations() -> Dict[str, any]:
    """
    Get timeframe recommendations for different trading strategies.

    Returns:
        Dictionary with timeframe groups and recommendations
    """
    manager = _get_timeframe_manager()
    available = manager.get_available_timeframes()

    return {
        "recommendations": {
            "scalping": {
                "timeframes": available["scalping"],
                "description": "High-frequency trading with micro trends",
                "risk_level": "High",
            },
            "day_trading": {
                "timeframes": available["day_trading"],
                "description": "Intraday swings, trend following within day",
                "risk_level": "Medium-High",
            },
            "swing_trading": {
                "timeframes": available["swing_trading"],
                "description": "Multi-day/week trends with good risk/reward",
                "risk_level": "Medium",
            },
            "position_trading": {
                "timeframes": available["position_trading"],
                "description": "Daily trends with strong signals (VALIDATED)",
                "risk_level": "Medium-Low",
            },
            "long_term": {
                "timeframes": available["intermediate_term"] + available["long_term"],
                "description": "Major trends and institutional moves",
                "risk_level": "Low",
            },
        },
        "default_recommended": "1d",
    }


# ============================================================================
# AUTOGEN TOOL METADATA
# ============================================================================

TIMEFRAME_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_timeframe",
            "description": "Get the currently active trading timeframe",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_current_timeframe",
            "description": "Change the active trading timeframe. For example, change from 1d to 4h for more frequent trading.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timeframe": {
                        "type": "string",
                        "description": "Timeframe to activate: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M",
                    }
                },
                "required": ["timeframe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_available_timeframes",
            "description": "List all available timeframes grouped by trading style",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_descriptions": {
                        "type": "boolean",
                        "description": "Include detailed descriptions of each timeframe",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_timeframe",
            "description": "Check if a timeframe string is valid",
            "parameters": {
                "type": "object",
                "properties": {
                    "timeframe": {
                        "type": "string",
                        "description": "Timeframe to validate",
                    }
                },
                "required": ["timeframe"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeframe_recommendations",
            "description": "Get recommended timeframes for different trading strategies (scalping, day trading, swing trading, etc)",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]
