"""
CLI Timeframe Commands (Issue #365)

Natural language commands for changing, querying, and validating timeframes.
Integrates with CLI LLM interface for user-friendly timeframe management.
"""

from typing import Dict, Optional

from src.trading.timeframe_tools import TimeframeManager


class TimeframeCommands:
    """CLI commands for timeframe management."""

    _instance = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(TimeframeCommands, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize timeframe commands."""
        if self._initialized:
            return
        self.manager = TimeframeManager()
        self._initialized = True

    def list_timeframes(self, verbose: bool = False) -> str:
        """
        List all available timeframes.

        Args:
            verbose: Show descriptions

        Returns:
            Formatted output string
        """
        timeframes = self.manager.list_timeframes(verbose=verbose)
        current = timeframes["current"]

        output = "📊 Available Timeframes:\n"
        output += "=" * 50 + "\n"

        if verbose:
            for item in timeframes["timeframes"]:
                marker = "✓" if item["current"] else " "
                output += f"  [{marker}] {item['tf']:5s} - {item['info']}\n"
        else:
            tf_list = ", ".join([f"'{tf}'" for tf in timeframes["timeframes"]])
            output += f"  {tf_list}\n"

        output += "\n" + "-" * 50 + "\n"
        output += f"📍 Current: {current}\n"

        return output

    def set_timeframe(self, timeframe: str) -> str:
        """
        Change the active timeframe.

        Args:
            timeframe: New timeframe

        Returns:
            Status message
        """
        result = self.manager.set_timeframe(timeframe)

        if result["success"]:
            return f"✅ {result['message']}"
        else:
            return f"❌ {result['message']}"

    def show_current_timeframe(self) -> str:
        """
        Show current timeframe.

        Returns:
            Formatted output
        """
        current = self.manager.get_current_timeframe()
        info = self.manager.get_timeframe_info(current)

        output = "📍 Current Timeframe\n"
        output += "=" * 50 + "\n"
        output += f"  {info['timeframe']}: {info['description']}\n"

        return output

    def show_timeframe_recommendations(self) -> str:
        """
        Show timeframe recommendations for different strategies.

        Returns:
            Formatted output
        """
        recs = self.manager.get_available_timeframes()

        output = "📈 Timeframe Recommendations\n"
        output += "=" * 50 + "\n"
        output += f"\n🎯 Scalping (Aggressive):\n"
        output += f"   {', '.join(recs['scalping'])}\n"
        output += f"\n📊 Day Trading (Intraday):\n"
        output += f"   {', '.join(recs['day_trading'])}\n"
        output += f"\n🔄 Swing Trading (Medium):\n"
        output += f"   {', '.join(recs['swing_trading'])}\n"
        output += f"\n📍 Position Trading (Recommended):\n"
        output += f"   {', '.join(recs['position_trading'])}\n"
        output += f"\n📈 Long-Term (Conservative):\n"
        output += f"   {', '.join(recs['intermediate_term'])} - {', '.join(recs['long_term'])}\n"

        return output

    def validate_and_info(self, timeframe: str) -> str:
        """
        Validate and show info about a timeframe.

        Args:
            timeframe: Timeframe to check

        Returns:
            Formatted output
        """
        validation = self.manager.validate_timeframe(timeframe)

        if not validation["valid"]:
            return f"❌ Invalid timeframe: {timeframe}\n\nValid options: {', '.join(validation['available'])}"

        info = self.manager.get_timeframe_info(timeframe)
        current = "📍 (current)" if info["current"] else ""

        output = f"ℹ️  {timeframe} {current}\n"
        output += "=" * 50 + "\n"
        output += f"{info['description']}\n"

        return output

    def get_for_agent(self, command: str, arg: Optional[str] = None) -> Dict:
        """
        Get timeframe data for agents (no display formatting).

        Args:
            command: Command to execute
            arg: Optional argument

        Returns:
            Dictionary suitable for agent consumption
        """
        if command == "current":
            return {
                "type": "current_timeframe",
                "timeframe": self.manager.get_current_timeframe(),
            }
        elif command == "set":
            return self.manager.set_timeframe(arg or "1d")
        elif command == "list":
            return self.manager.list_timeframes(verbose=arg == "verbose")
        elif command == "validate":
            return self.manager.validate_timeframe(arg or "")
        elif command == "info":
            return self.manager.get_timeframe_info(arg or "")
        elif command == "recommendations":
            return self.manager.get_available_timeframes()
        else:
            return {"error": f"Unknown command: {command}"}


def get_timeframe_commands() -> TimeframeCommands:
    """Get singleton instance of TimeframeCommands."""
    return TimeframeCommands()
