"""
Interactive Help System for Trading CLI

Issue #369: Interactive Help System for CLI
Provides searchable, context-aware help for all trading commands.

Features:
- `/help` - Show all commands grouped by category
- `/help COMMAND` - Show specific command help
- `/help search KEYWORD` - Search help by keyword
- `/help --examples` - Show all examples
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class HelpSystem:
    """Interactive help system with searchable documentation."""

    def __init__(self):
        """Initialize help system with command documentation."""
        self.commands = self._build_help_data()
        self.categories = self._extract_categories()

    def _build_help_data(self) -> Dict[str, Dict]:
        """Build comprehensive help data for all commands."""
        return {
            # ==================== WORKFLOW COMMANDS ====================
            "morning-routine": {
                "category": "Workflow",
                "description": "Run morning market scan and analysis",
                "usage": "morning-routine [symbols]",
                "examples": [
                    "morning-routine",
                    "morning-routine AAPL,MSFT,TSLA",
                    "morning-routine --approve-all",
                ],
                "aliases": ["morning", "scan"],
                "tags": ["workflow", "scanning", "analysis"],
                "related": ["approve", "reject", "monitor", "evening-summary"],
                "details": (
                    "Scans your watchlist for trading opportunities using technical analysis.\n"
                    "Shows buy/sell signals with confidence levels.\n"
                    "Enters approval mode if execution_mode is set to CONFIRM.\n\n"
                    "Options:\n"
                    "  --approve-all    Auto-approve all pending trades\n"
                    "  --paper          Run in paper trading mode only"
                ),
            },
            "approve": {
                "category": "Workflow",
                "description": "Approve a pending trade",
                "usage": "approve SYMBOL | approve all",
                "examples": [
                    "approve AAPL",
                    "approve all",
                ],
                "aliases": ["yes", "ok"],
                "tags": ["workflow", "execution"],
                "related": ["reject", "morning-routine", "show orders"],
                "details": (
                    "Approves a pending trade for execution.\n"
                    "After approval, the trade is executed using your current execution mode.\n\n"
                    "Use 'approve all' to approve all pending trades at once."
                ),
            },
            "reject": {
                "category": "Workflow",
                "description": "Reject a pending trade",
                "usage": "reject SYMBOL | reject all",
                "examples": [
                    "reject MSFT",
                    "reject all",
                ],
                "aliases": ["no", "skip"],
                "tags": ["workflow", "execution"],
                "related": ["approve", "morning-routine"],
                "details": (
                    "Rejects a pending trade without executing it.\n"
                    "The signal is logged for analysis but not traded.\n\n"
                    "Use 'reject all' to reject all pending trades at once."
                ),
            },
            "monitor": {
                "category": "Workflow",
                "description": "Monitor active positions",
                "usage": "monitor [--check-exits]",
                "examples": [
                    "monitor",
                    "monitor --check-exits",
                ],
                "aliases": ["watch", "positions"],
                "tags": ["workflow", "monitoring"],
                "related": ["show portfolio", "show positions", "evening-summary"],
                "details": (
                    "Continuously monitors your active trading positions.\n"
                    "Displays position updates, profit/loss, and exit signals.\n\n"
                    "Options:\n"
                    "  --check-exits    Check for exit signals on open positions\n"
                    "  --interval 5     Update every N minutes (default: 5)"
                ),
            },
            "evening-summary": {
                "category": "Workflow",
                "description": "Generate end-of-day report",
                "usage": "evening-summary [--save FILE]",
                "examples": [
                    "evening-summary",
                    "evening-summary --save report.txt",
                ],
                "aliases": ["summary", "report", "eod"],
                "tags": ["workflow", "reporting"],
                "related": ["morning-routine", "show portfolio"],
                "details": (
                    "Generates a comprehensive end-of-day report.\n"
                    "Includes trades executed, P&L, market insights, and next steps.\n\n"
                    "Options:\n"
                    "  --save FILE      Save report to file\n"
                    "  --detailed       Include detailed trade breakdown"
                ),
            },
            # ==================== TRADING COMMANDS ====================
            "buy": {
                "category": "Trading",
                "description": "Place a manual buy order",
                "usage": "buy SYMBOL QUANTITY [PRICE]",
                "examples": [
                    "buy AAPL 10",
                    "buy MSFT 5 $425.50",
                ],
                "aliases": ["long"],
                "tags": ["trading", "execution"],
                "related": ["sell", "show orders", "cancel"],
                "details": (
                    "Place a buy order for a specific symbol and quantity.\n"
                    "If price is not specified, uses current market price.\n"
                    "Respects risk management rules and position limits.\n\n"
                    "Execution depends on current execution_mode:\n"
                    "  CONFIRM - Asks for approval before executing\n"
                    "  AUTO    - Executes immediately\n"
                    "  PAPER   - Simulates the trade without real money\n"
                    "  DISABLED - Blocks all trading"
                ),
            },
            "sell": {
                "category": "Trading",
                "description": "Place a manual sell order",
                "usage": "sell SYMBOL QUANTITY [PRICE]",
                "examples": [
                    "sell AAPL 10",
                    "sell MSFT 5 $427.00",
                ],
                "aliases": ["close", "exit"],
                "tags": ["trading", "execution"],
                "related": ["buy", "show orders", "cancel"],
                "details": (
                    "Place a sell order to close a position.\n"
                    "You can only sell if you own the position.\n"
                    "If price is not specified, uses current market price.\n\n"
                    "Note: To short sell (sell without owning), use 'short' command."
                ),
            },
            "cancel": {
                "category": "Trading",
                "description": "Cancel pending or open orders",
                "usage": "cancel ORDER_ID | cancel SYMBOL | cancel all",
                "examples": [
                    "cancel 12345",
                    "cancel AAPL",
                    "cancel all",
                ],
                "aliases": ["delete", "remove"],
                "tags": ["trading", "order management"],
                "related": ["show orders", "buy", "sell"],
                "details": (
                    "Cancel one or more pending orders.\n\n"
                    "Usage:\n"
                    "  cancel ORDER_ID  - Cancel specific order by ID\n"
                    "  cancel SYMBOL    - Cancel all orders for a symbol\n"
                    "  cancel all       - Cancel all pending orders (with confirmation)\n\n"
                    "Note: Canceled orders are logged for record-keeping."
                ),
            },
            # ==================== INFORMATION COMMANDS ====================
            "show portfolio": {
                "category": "Information",
                "description": "Show portfolio summary and allocation",
                "usage": "show portfolio [--detailed]",
                "examples": [
                    "show portfolio",
                    "show portfolio --detailed",
                ],
                "aliases": ["portfolio", "positions overview"],
                "tags": ["information", "portfolio"],
                "related": ["show positions", "show orders", "show account"],
                "details": (
                    "Display portfolio summary including:\n"
                    "  - Total portfolio value\n"
                    "  - Cash available\n"
                    "  - Position allocation\n"
                    "  - Daily P&L\n"
                    "  - Risk metrics\n\n"
                    "Use --detailed for full breakdown by symbol."
                ),
            },
            "show positions": {
                "category": "Information",
                "description": "Show open positions with details",
                "usage": "show positions [SYMBOL]",
                "examples": [
                    "show positions",
                    "show positions AAPL",
                ],
                "aliases": ["positions", "holdings"],
                "tags": ["information", "portfolio"],
                "related": ["show portfolio", "show orders", "monitor"],
                "details": (
                    "Display all open positions with:\n"
                    "  - Entry price and quantity\n"
                    "  - Current price and P&L\n"
                    "  - Stop loss and take profit levels\n"
                    "  - Position duration\n\n"
                    "Optionally filter by symbol."
                ),
            },
            "show orders": {
                "category": "Information",
                "description": "Show open and closed orders",
                "usage": "show orders [--detailed] [SYMBOL]",
                "examples": [
                    "show orders",
                    "show orders --detailed",
                    "show orders AAPL",
                ],
                "aliases": ["orders", "order history"],
                "tags": ["information", "orders"],
                "related": ["show positions", "cancel", "buy", "sell"],
                "details": (
                    "Display order history including:\n"
                    "  - Open orders with status\n"
                    "  - Closed orders from today\n"
                    "  - Entry and exit prices\n"
                    "  - P&L for completed trades\n\n"
                    "Use --detailed for full order details including stops/targets."
                ),
            },
            "show account": {
                "category": "Information",
                "description": "Show account details and limits",
                "usage": "show account",
                "examples": [
                    "show account",
                ],
                "aliases": ["account", "account info"],
                "tags": ["information", "account"],
                "related": ["show portfolio", "show positions"],
                "details": (
                    "Display account information:\n"
                    "  - Account type (paper/live)\n"
                    "  - Total equity\n"
                    "  - Available cash\n"
                    "  - Buying power\n"
                    "  - Account restrictions"
                ),
            },
            # ==================== CONFIGURATION COMMANDS ====================
            "set execution-mode": {
                "category": "Configuration",
                "description": "Set trading execution mode",
                "usage": "set execution-mode {confirm|auto|paper|disabled}",
                "examples": [
                    "set execution-mode confirm",
                    "set execution-mode auto",
                    "set execution-mode paper",
                ],
                "aliases": ["set mode", "execution mode"],
                "tags": ["configuration", "trading"],
                "related": ["show execution-mode"],
                "details": (
                    "Change how trades are executed:\n\n"
                    "  CONFIRM  - Ask for approval before each trade (default)\n"
                    "  AUTO     - Execute trades automatically without approval\n"
                    "  PAPER    - Simulate trades without real money (testing)\n"
                    "  DISABLED - Block all trading\n\n"
                    "⚠️  WARNING: Switching from paper to auto/confirm requires confirmation."
                ),
            },
            "show execution-mode": {
                "category": "Configuration",
                "description": "Show current execution mode",
                "usage": "show execution-mode",
                "examples": [
                    "show execution-mode",
                ],
                "aliases": ["show mode", "mode"],
                "tags": ["configuration"],
                "related": ["set execution-mode"],
                "details": (
                    "Display the current trading execution mode.\n"
                    "This determines how your trades are processed."
                ),
            },
            "set voter-system": {
                "category": "Configuration",
                "description": "Switch between voter systems",
                "usage": "set voter-system {single|ranked}",
                "examples": [
                    "set voter-system single",
                    "set voter-system ranked",
                ],
                "aliases": ["voter system"],
                "tags": ["configuration", "analysis"],
                "related": ["show config"],
                "details": (
                    "Choose which voting system to use for signals:\n\n"
                    "  SINGLE - Simple MACD+RSI voting (fast, tested)\n"
                    "  RANKED - Multi-indicator consensus voting (more signals)\n\n"
                    "Ranked voter uses multiple indicators for higher confidence."
                ),
            },
            "show config": {
                "category": "Configuration",
                "description": "Show current configuration",
                "usage": "show config [--all]",
                "examples": [
                    "show config",
                    "show config --all",
                ],
                "aliases": ["config", "settings"],
                "tags": ["configuration", "information"],
                "related": ["set execution-mode", "set voter-system"],
                "details": (
                    "Display current system configuration including:\n"
                    "  - Execution mode\n"
                    "  - Risk parameters\n"
                    "  - Indicator parameters\n"
                    "  - Position limits\n\n"
                    "Use --all to see all available config options."
                ),
            },
            # ==================== HELP & SYSTEM COMMANDS ====================
            "help": {
                "category": "Help",
                "description": "Show interactive help",
                "usage": "/help [COMMAND] [--search KEYWORD]",
                "examples": [
                    "/help",
                    "/help morning-routine",
                    "/help search workflow",
                    "/help --examples",
                ],
                "aliases": ["?", "h"],
                "tags": ["help", "documentation"],
                "related": [],
                "details": (
                    "Get help on commands.\n\n"
                    "Usage:\n"
                    "  /help                - Show all commands by category\n"
                    "  /help COMMAND        - Show help for specific command\n"
                    "  /help search KEYWORD - Search commands by keyword\n"
                    "  /help --examples     - Show all command examples\n\n"
                    "Type '/help COMMAND' to see detailed help for any command."
                ),
            },
            "exit": {
                "category": "Help",
                "description": "Exit the trading CLI",
                "usage": "exit | quit",
                "examples": [
                    "exit",
                    "quit",
                ],
                "aliases": ["quit", "q"],
                "tags": ["help", "system"],
                "related": [],
                "details": (
                    "Exit the interactive CLI session.\n"
                    "All positions remain active - exiting the CLI doesn't close trades.\n"
                    "Use 'sell' or 'cancel' to close positions before exiting."
                ),
            },
        }

    def _extract_categories(self) -> Dict[str, List[str]]:
        """Extract unique categories from command data."""
        categories = {}
        for command, data in self.commands.items():
            category = data.get("category", "Other")
            if category not in categories:
                categories[category] = []
            categories[category].append(command)
        return categories

    def get_help_all(self) -> str:
        """Get help for all commands grouped by category."""
        output = []
        output.append("╔════════════════════════════════════════════════════════════════╗")
        output.append("║           AUTOGEN-TRADER INTERACTIVE CLI - HELP MENU            ║")
        output.append("╚════════════════════════════════════════════════════════════════╝\n")

        for category in sorted(self.categories.keys()):
            output.append(f"\n{category.upper()}")
            output.append("─" * 50)

            for command in sorted(self.categories[category]):
                data = self.commands[command]
                desc = data.get("description", "No description")
                output.append(f"  {command:25} {desc}")

            output.append("")

        output.append("Type '/help COMMAND' for detailed help on any command")
        output.append("Type '/help search KEYWORD' to search for commands")
        output.append("Type '/help --examples' to see command examples")

        return "\n".join(output)

    def get_help_command(self, command: str) -> str:
        """Get detailed help for a specific command."""
        # Handle partial command names
        matching = [cmd for cmd in self.commands.keys() if cmd.startswith(command.lower())]

        if not matching:
            return f"❌ Command '{command}' not found. Type '/help' to see all commands."

        if len(matching) > 1:
            return f"❓ Ambiguous: '{command}' matches: {', '.join(matching)}"

        cmd = matching[0]
        data = self.commands[cmd]

        output = []
        output.append("╔════════════════════════════════════════════════════════════════╗")
        output.append(f"║ {cmd.upper():62} ║")
        output.append("╚════════════════════════════════════════════════════════════════╝\n")

        output.append(f"{data.get('description', 'No description')}\n")

        output.append("USAGE:")
        output.append(f"  {data.get('usage', 'N/A')}\n")

        if data.get("examples"):
            output.append("EXAMPLES:")
            for example in data["examples"]:
                output.append(f"  > {example}")
            output.append("")

        if data.get("aliases"):
            output.append(f"ALIASES: {', '.join(data['aliases'])}")
            output.append("")

        if data.get("details"):
            output.append("DETAILS:")
            output.append(data["details"])
            output.append("")

        if data.get("related"):
            output.append(f"RELATED: {', '.join(data['related'])}")

        return "\n".join(output)

    def search_help(self, keyword: str) -> str:
        """Search help by keyword."""
        keyword = keyword.lower()
        matches = []

        for command, data in self.commands.items():
            # Search in description, usage, tags, and details
            if (
                keyword in data.get("description", "").lower()
                or keyword in data.get("usage", "").lower()
                or keyword in " ".join(data.get("tags", [])).lower()
                or keyword in " ".join(data.get("aliases", [])).lower()
                or keyword in data.get("details", "").lower()
            ):
                matches.append(command)

        if not matches:
            return f"❌ No commands found matching '{keyword}'"

        output = []
        output.append(f"SEARCH RESULTS for '{keyword}' ({len(matches)} found):\n")

        for cmd in sorted(matches):
            data = self.commands[cmd]
            desc = data.get("description", "")
            output.append(f"  {cmd:25} {desc}")

        output.append("")
        output.append("Type '/help COMMAND' for detailed help on any command")

        return "\n".join(output)

    def get_examples(self) -> str:
        """Get all examples."""
        output = []
        output.append("╔════════════════════════════════════════════════════════════════╗")
        output.append("║                      COMMAND EXAMPLES                          ║")
        output.append("╚════════════════════════════════════════════════════════════════╝\n")

        for category in sorted(self.categories.keys()):
            output.append(f"{category.upper()}")
            output.append("─" * 50)

            for command in sorted(self.categories[category]):
                data = self.commands[command]
                if data.get("examples"):
                    output.append(f"\n{command}:")
                    for example in data["examples"]:
                        output.append(f"  > {example}")

            output.append("")

        return "\n".join(output)

    def handle_help_command(self, input_str: str) -> str:
        """
        Handle help command from user input.

        Formats:
        - /help
        - /help COMMAND
        - /help search KEYWORD
        - /help --examples
        """
        parts = input_str.strip().split(None, 2)

        if len(parts) == 1:
            # Just /help
            return self.get_help_all()

        if len(parts) >= 2:
            if parts[1] == "search" and len(parts) >= 3:
                # /help search KEYWORD
                return self.search_help(parts[2])
            elif parts[1] == "--examples":
                # /help --examples
                return self.get_examples()
            else:
                # /help COMMAND
                return self.get_help_command(parts[1])

        return self.get_help_all()
