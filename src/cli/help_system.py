"""
Help System for CLI - Searchable, organized command documentation.

Issue #369: Interactive manual/help system with search

Provides:
- Categorized command reference
- Searchable help by keyword
- Examples for each command
- Command aliases and related commands
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class CommandHelp:
    """Help information for a single command."""

    name: str
    description: str
    usage: str
    examples: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    category: str = "general"
    tags: Set[str] = field(default_factory=set)
    related: List[str] = field(default_factory=list)
    notes: Optional[str] = None


class HelpSystem:
    """
    Interactive help system with search and categorization.

    Features:
    - Command categorization (workflow, trading, status, config, system)
    - Keyword search across all commands
    - Related command suggestions
    - Examples for each command
    """

    def __init__(self):
        """Initialize help system with all command documentation."""
        self.commands: Dict[str, CommandHelp] = {}
        self.categories: Dict[str, List[str]] = {}
        self._register_all_commands()

    def _register_all_commands(self):
        """Register all CLI commands with help information."""

        # === SYSTEM COMMANDS ===
        self._register_command(
            CommandHelp(
                name="/help",
                description="Show this help message or help for specific command",
                usage="/help [command] | /help search KEYWORD",
                examples=[
                    "/help",
                    "/help buy",
                    "/help search order",
                    "/help search morning",
                ],
                aliases=[],
                category="system",
                tags={"help", "documentation", "search"},
                related=[],
                notes="Use '/help search' to find commands by keyword",
            )
        )

        self._register_command(
            CommandHelp(
                name="/exit",
                description="Exit the CLI session",
                usage="/exit | /quit",
                examples=["/exit", "/quit"],
                aliases=["/quit"],
                category="system",
                tags={"exit", "quit", "close"},
                related=[],
            )
        )

        self._register_command(
            CommandHelp(
                name="/toggle",
                description="Toggle between CONFIRM and AUTO execution modes",
                usage="/toggle",
                examples=["/toggle"],
                aliases=[],
                category="system",
                tags={"mode", "execution", "confirm", "auto"},
                related=["set execution-mode"],
                notes="CONFIRM mode requires approval, AUTO mode executes immediately",
            )
        )

        self._register_command(
            CommandHelp(
                name="/tips",
                description="Show trading basics and educational tips for beginners",
                usage="/tips | /learn",
                examples=["/tips", "/learn"],
                aliases=["/learn"],
                category="system",
                tags={"education", "help", "basics", "beginner"},
                related=["/help"],
            )
        )

        self._register_command(
            CommandHelp(
                name="/schedule",
                description="Enter scheduler management mode",
                usage="/schedule",
                examples=["/schedule"],
                aliases=[],
                category="system",
                tags={"scheduler", "automation", "routine"},
                related=["show scheduler status"],
            )
        )

        # === TRADING COMMANDS (Natural Language) ===
        self._register_command(
            CommandHelp(
                name="buy",
                description="Execute a buy order for a stock",
                usage="buy [shares] SYMBOL [at/limit PRICE]",
                examples=[
                    "buy 10 AAPL",
                    "buy 5 MSFT at 420",
                    "buy 100 shares of TSLA",
                    "I want to buy META",
                ],
                aliases=["purchase", "long", "enter position"],
                category="trading",
                tags={"buy", "order", "trade", "long", "purchase"},
                related=["sell", "cancel", "show orders"],
                notes="System uses LLM parsing, so natural language works. Bracket orders (stop/target) are automatic.",
            )
        )

        self._register_command(
            CommandHelp(
                name="sell",
                description="Sell existing position or short a stock",
                usage="sell [shares] SYMBOL",
                examples=[
                    "sell AAPL",
                    "sell 10 MSFT",
                    "sell all my TSLA",
                    "close my META position",
                ],
                aliases=["close position", "exit trade"],
                category="trading",
                tags={"sell", "close", "exit", "order"},
                related=["buy", "show positions", "show orders"],
                notes="To sell a position you must own it first. Use '/tips' for more on shorting.",
            )
        )

        self._register_command(
            CommandHelp(
                name="cancel",
                description="Cancel an existing order",
                usage="cancel ORDER_ID | cancel SYMBOL | cancel all",
                examples=[
                    "cancel 12345",
                    "cancel AAPL",
                    "cancel all",
                    "cancel all pending",
                ],
                aliases=["cancel order"],
                category="trading",
                tags={"cancel", "order", "remove"},
                related=["show orders"],
                notes="Requires confirmation before canceling all orders",
            )
        )

        # === STATUS / QUERY COMMANDS (Natural Language) ===
        self._register_command(
            CommandHelp(
                name="show portfolio",
                description="Display portfolio overview with account value and P&L",
                usage="show portfolio | show account | check my portfolio",
                examples=[
                    "show portfolio",
                    "show my account",
                    "what's my portfolio status",
                    "how am I doing",
                ],
                aliases=["show account", "portfolio status", "account status"],
                category="status",
                tags={"portfolio", "account", "status", "balance", "pnl"},
                related=["show positions", "show orders"],
            )
        )

        self._register_command(
            CommandHelp(
                name="show positions",
                description="Display all active positions with current P&L",
                usage="show positions | show my positions | what positions do I have",
                examples=[
                    "show positions",
                    "show my positions",
                    "what stocks do I own",
                    "check my holdings",
                ],
                aliases=["show holdings", "my positions"],
                category="status",
                tags={"positions", "holdings", "stocks", "pnl"},
                related=["show portfolio", "show orders"],
            )
        )

        self._register_command(
            CommandHelp(
                name="show orders",
                description="Display open and recent orders with stops/targets",
                usage="show orders [SYMBOL] | show orders --detailed",
                examples=[
                    "show orders",
                    "show my orders",
                    "show orders AAPL",
                    "show orders --detailed",
                ],
                aliases=["my orders", "open orders"],
                category="status",
                tags={"orders", "trades", "stops", "targets"},
                related=["show positions", "cancel"],
                notes="Use --detailed to see full bracket order information (stop/target prices)",
            )
        )

        self._register_command(
            CommandHelp(
                name="check my alerts",
                description="Show position alerts for stop-loss and take-profit levels",
                usage="check my alerts | show alerts | check stops",
                examples=[
                    "check my alerts",
                    "show my alerts",
                    "are any stops close",
                    "check my stop losses",
                ],
                aliases=["show alerts", "check stops", "check targets"],
                category="status",
                tags={"alerts", "stops", "targets", "risk"},
                related=["show positions", "show orders"],
            )
        )

        # === CONFIG COMMANDS ===
        self._register_command(
            CommandHelp(
                name="set execution-mode",
                description="Set trading execution mode (confirm, auto, paper, disabled)",
                usage="set execution-mode {confirm|auto|paper|disabled}",
                examples=[
                    "set execution-mode confirm",
                    "set execution-mode auto",
                    "set execution-mode paper",
                    "set execution-mode disabled",
                ],
                aliases=["set mode"],
                category="config",
                tags={"mode", "execution", "confirm", "auto", "paper"},
                related=["/toggle", "show execution-mode"],
                notes="CONFIRM=human approval, AUTO=autonomous, PAPER=simulation, DISABLED=trading off",
            )
        )

        self._register_command(
            CommandHelp(
                name="show execution-mode",
                description="Display current execution mode",
                usage="show execution-mode | show mode",
                examples=["show execution-mode", "show mode", "what mode am I in"],
                aliases=["show mode"],
                category="config",
                tags={"mode", "execution", "status"},
                related=["set execution-mode", "/toggle"],
            )
        )

        self._register_command(
            CommandHelp(
                name="show config",
                description="Display current trading configuration",
                usage="show config",
                examples=["show config", "show configuration", "show settings"],
                aliases=["show configuration", "show settings"],
                category="config",
                tags={"config", "settings", "parameters"},
                related=["show execution-mode"],
            )
        )

        # === WORKFLOW COMMANDS (To be implemented by B) ===
        self._register_command(
            CommandHelp(
                name="morning-routine",
                description="Run morning market scan and analysis workflow",
                usage="morning-routine [SYMBOLS] | morning-routine --auto-approve",
                examples=[
                    "morning-routine",
                    "morning-routine AAPL,MSFT,TSLA",
                    "morning-routine --auto-approve",
                ],
                aliases=["morning", "scan", "morning scan"],
                category="workflow",
                tags={"workflow", "morning", "scan", "routine", "analysis"},
                related=["approve", "reject", "evening-summary"],
                notes="Scans markets, generates signals, analyzes risk. Awaits approval in CONFIRM mode.",
            )
        )

        self._register_command(
            CommandHelp(
                name="approve",
                description="Approve pending trade(s) from morning routine",
                usage="approve SYMBOL | approve all",
                examples=["approve AAPL", "approve all", "approve MSFT"],
                aliases=["execute", "go ahead"],
                category="workflow",
                tags={"approve", "execute", "confirm", "workflow"},
                related=["reject", "morning-routine", "show execution-mode"],
                notes="Only available in CONFIRM mode with pending trades",
            )
        )

        self._register_command(
            CommandHelp(
                name="reject",
                description="Reject pending trade(s) from morning routine",
                usage="reject SYMBOL | reject all",
                examples=["reject AAPL", "reject all", "reject MSFT"],
                aliases=["skip", "pass"],
                category="workflow",
                tags={"reject", "skip", "cancel", "workflow"},
                related=["approve", "morning-routine"],
                notes="Only available in CONFIRM mode with pending trades",
            )
        )

        self._register_command(
            CommandHelp(
                name="monitor",
                description="Monitor active positions for exit signals",
                usage="monitor | monitor --check-exits",
                examples=["monitor", "monitor --check-exits", "check positions"],
                aliases=["check positions"],
                category="workflow",
                tags={"monitor", "positions", "exits", "workflow"},
                related=["show positions", "evening-summary"],
                notes="Continuously monitors positions, checks for exit signals based on indicators",
            )
        )

        self._register_command(
            CommandHelp(
                name="evening-summary",
                description="Generate end-of-day trading summary and P&L report",
                usage="evening-summary | evening-summary --save FILENAME",
                examples=[
                    "evening-summary",
                    "evening-summary --save report.txt",
                    "end of day summary",
                ],
                aliases=["evening", "eod", "end of day"],
                category="workflow",
                tags={"evening", "summary", "report", "workflow", "eod"},
                related=["morning-routine", "show portfolio"],
                notes="Generates comprehensive report of day's trading activity",
            )
        )

        self._register_command(
            CommandHelp(
                name="show scheduler status",
                description="Display scheduler status and scheduled routines",
                usage="show scheduler status | show scheduler",
                examples=["show scheduler status", "show scheduler", "scheduler status"],
                aliases=["scheduler status"],
                category="workflow",
                tags={"scheduler", "status", "automation"},
                related=["/schedule", "morning-routine", "evening-summary"],
            )
        )

    def _register_command(self, cmd_help: CommandHelp):
        """Register a command with its help information."""
        self.commands[cmd_help.name] = cmd_help

        # Add to category
        if cmd_help.category not in self.categories:
            self.categories[cmd_help.category] = []
        self.categories[cmd_help.category].append(cmd_help.name)

        # Register aliases
        for alias in cmd_help.aliases:
            self.commands[alias] = cmd_help

    def get_help(self, command: Optional[str] = None) -> str:
        """
        Get help for a specific command or show all commands.

        Args:
            command: Command name (with or without /) or None for all

        Returns:
            Formatted help text
        """
        if command is None:
            return self._format_all_help()

        # Clean command name
        cmd = command.lower().strip().lstrip("/")

        # Try exact match
        if cmd in self.commands:
            return self._format_command_help(self.commands[cmd])

        # Try partial match
        matches = [name for name in self.commands.keys() if cmd in name.lower()]
        if len(matches) == 1:
            return self._format_command_help(self.commands[matches[0]])
        elif len(matches) > 1:
            return (
                f"Multiple commands match '{command}':\n"
                + "\n".join(f"  - {m}" for m in matches)
                + "\n\nUse '/help COMMAND' for specific help"
            )

        return f"Unknown command: {command}\n\nUse '/help' to see all commands"

    def search(self, keyword: str) -> str:
        """
        Search commands by keyword.

        Args:
            keyword: Search term

        Returns:
            Formatted search results
        """
        keyword_lower = keyword.lower()
        matches = []

        for cmd_help in self.commands.values():
            # Avoid duplicates from aliases
            if cmd_help.name in [m.name for m in matches]:
                continue

            # Search in name, description, tags
            if (
                keyword_lower in cmd_help.name.lower()
                or keyword_lower in cmd_help.description.lower()
                or any(keyword_lower in tag.lower() for tag in cmd_help.tags)
            ):
                matches.append(cmd_help)

        if not matches:
            return f"No commands found matching '{keyword}'"

        result = [f"Commands matching '{keyword}':\n"]
        for cmd_help in matches:
            result.append(f"  {cmd_help.name:25} - {cmd_help.description}")

        result.append(f"\n{len(matches)} commands found. Use '/help COMMAND' for details")
        return "\n".join(result)

    def _format_all_help(self) -> str:
        """Format help for all commands, organized by category."""
        lines = []
        lines.append("=" * 80)
        lines.append("AVAILABLE COMMANDS")
        lines.append("=" * 80)

        # Category order
        category_order = ["workflow", "trading", "status", "config", "system"]
        category_titles = {
            "workflow": "WORKFLOW - Daily trading routines",
            "trading": "TRADING - Execute trades",
            "status": "STATUS - Check positions and portfolio",
            "config": "CONFIG - Configuration and settings",
            "system": "SYSTEM - CLI controls",
        }

        for category in category_order:
            if category not in self.categories:
                continue

            lines.append(f"\n{category_titles.get(category, category.upper())}")
            lines.append("-" * 80)

            # Get unique commands (skip aliases)
            seen = set()
            for cmd_name in self.categories[category]:
                cmd_help = self.commands[cmd_name]
                if cmd_help.name in seen:
                    continue
                seen.add(cmd_help.name)

                lines.append(f"  {cmd_help.name:25} - {cmd_help.description}")

        lines.append("\n" + "=" * 80)
        lines.append("Type '/help COMMAND' for details on a specific command")
        lines.append("Type '/help search KEYWORD' to search commands")
        lines.append("Type '/tips' for trading basics")
        lines.append("=" * 80)

        return "\n".join(lines)

    def _format_command_help(self, cmd_help: CommandHelp) -> str:
        """Format detailed help for a specific command."""
        lines = []
        lines.append("=" * 80)
        lines.append(f"{cmd_help.name} - {cmd_help.description}")
        lines.append("=" * 80)

        lines.append("\nUsage:")
        lines.append(f"  {cmd_help.usage}")

        if cmd_help.examples:
            lines.append("\nExamples:")
            for example in cmd_help.examples:
                lines.append(f"  > {example}")

        if cmd_help.aliases:
            lines.append(f"\nAliases: {', '.join(cmd_help.aliases)}")

        if cmd_help.notes:
            lines.append("\nNotes:")
            lines.append(f"  {cmd_help.notes}")

        if cmd_help.related:
            lines.append(f"\nSee also: {', '.join(cmd_help.related)}")

        lines.append("=" * 80)

        return "\n".join(lines)

    def get_commands_by_category(self, category: str) -> List[str]:
        """Get all command names in a category."""
        return self.categories.get(category, [])

    def get_all_categories(self) -> List[str]:
        """Get list of all categories."""
        return list(self.categories.keys())
