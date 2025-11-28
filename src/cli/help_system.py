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
        self.commands = self._load_help_data()
        self.categories = self._extract_categories()

    def _load_help_data(self) -> Dict[str, Dict]:
        """Load help data from YAML configuration file."""
        import os

        import yaml

        config_path = os.path.join(
            os.path.dirname(__file__), "../../config_defaults/help_commands.yaml"
        )

        try:
            with open(config_path, encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load help commands from YAML: {e}")
            print("Falling back to hardcoded commands...")
            return self._build_help_data_fallback()

    def _build_help_data_fallback(self) -> Dict[str, Dict]:
        """Build comprehensive help data for all commands (DEPRECATED - use YAML)."""
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
                "usage": "buy SYMBOL QUANTITY [PRICE] | buy SYMBOL [at a pullback/breakout]",
                "examples": [
                    "buy AAPL 10",
                    "buy MSFT 5 $425.50",
                    "buy QQQ at a pullback",
                    "buy SPY on a dip",
                    "buy NVDA at a breakout",
                ],
                "aliases": ["long"],
                "tags": ["trading", "execution", "timing"],
                "related": ["sell", "show orders", "cancel"],
                "details": (
                    "Place a buy order for a specific symbol and quantity.\n"
                    "If price is not specified, uses current market price.\n"
                    "Respects risk management rules and position limits.\n\n"
                    "NEW: Entry Timing Context (Issue #344):\n"
                    "  'at a pullback' or 'on a dip' - Entry 2.5% below current price\n"
                    "  'at a breakout' - Entry 1.5% above current price\n"
                    "  'now' or immediate - Entry at current market price\n\n"
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
                "aliases": ["execution mode"],
                "tags": ["configuration", "trading"],
                "related": ["set execution-mode"],
                "details": "Display the current trading execution mode setting.",
            },
            "change timeframe": {
                "category": "Configuration",
                "description": "Change analysis timeframe (Issue #365)",
                "usage": "change timeframe to {1m|5m|15m|30m|1h|2h|4h|1d|1w|1M}",
                "examples": [
                    "change timeframe to 1h",
                    "set timeframe 4h",
                    "switch to 5m",
                    "use 1d timeframe",
                ],
                "aliases": ["set timeframe", "switch timeframe", "use timeframe"],
                "tags": ["configuration", "analysis", "timeframe"],
                "related": ["show timeframe", "list timeframes", "timeframe recommendations"],
                "details": (
                    "Change the active timeframe for technical analysis:\n\n"
                    "Scalping (aggressive):     1m, 5m\n"
                    "Day Trading (intraday):    15m, 30m\n"
                    "Swing Trading (medium):    1h, 2h, 4h\n"
                    "Position Trading (default): 1d (validated 0.856 Sharpe)\n"
                    "Long-term:                 1w, 1M\n\n"
                    "The timeframe determines the candle period for MACD and RSI indicators.\n"
                    "Default '1d' has been validated with the best performance."
                ),
            },
            "show timeframe": {
                "category": "Configuration",
                "description": "Show current timeframe",
                "usage": "show timeframe | current timeframe",
                "examples": [
                    "show timeframe",
                    "current timeframe",
                    "what timeframe",
                ],
                "aliases": ["current timeframe", "active timeframe"],
                "tags": ["configuration", "analysis", "timeframe"],
                "related": ["change timeframe", "list timeframes"],
                "details": "Display the currently active timeframe for analysis.",
            },
            "list timeframes": {
                "category": "Configuration",
                "description": "List all available timeframes",
                "usage": "list timeframes [verbose]",
                "examples": [
                    "list timeframes",
                    "show available timeframes",
                    "list timeframes verbose",
                ],
                "aliases": ["show timeframes", "available timeframes"],
                "tags": ["configuration", "analysis", "timeframe"],
                "related": ["change timeframe", "show timeframe", "timeframe recommendations"],
                "details": (
                    "List all enabled timeframes with optional descriptions.\n\n"
                    "Use 'verbose' to see detailed descriptions of each timeframe."
                ),
            },
            "timeframe recommendations": {
                "category": "Configuration",
                "description": "Get timeframe recommendations by strategy",
                "usage": "timeframe recommendations",
                "examples": [
                    "timeframe recommendations",
                    "suggest timeframe",
                    "best timeframe for swing trading",
                ],
                "aliases": ["suggest timeframe", "recommend timeframe"],
                "tags": ["configuration", "analysis", "timeframe"],
                "related": ["change timeframe", "list timeframes"],
                "details": (
                    "Show recommended timeframes grouped by trading strategy:\n\n"
                    "  Scalping - 1m, 5m (high frequency, micro trends)\n"
                    "  Day Trading - 15m, 30m (intraday swings)\n"
                    "  Swing Trading - 1h, 2h, 4h (multi-day trends)\n"
                    "  Position Trading - 1d (validated default, best Sharpe)\n"
                    "  Long-term - 1w, 1M (institutional moves)\n\n"
                    "Use this to find the best timeframe for your trading style."
                ),
            },
            # Closing the previous entry that was broken
            "mode": {
                "category": "Configuration",
                "description": "Show current execution mode",
                "usage": "mode",
                "examples": ["mode"],
                "aliases": ["show mode"],
                "tags": ["configuration"],
                "related": ["set execution-mode", "show execution-mode"],
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
            # ==================== FORWARD TESTING COMMANDS ====================
            "forward-test start": {
                "category": "Testing",
                "description": "Start a new 30-day forward test",
                "usage": "forward-test start TEST_NAME [--capital AMOUNT]",
                "examples": [
                    "forward-test start production_validation_2025",
                    "forward-test start my_test --capital 10000",
                ],
                "aliases": ["ftest start", "test start"],
                "tags": ["testing", "validation", "forward-testing"],
                "related": ["forward-test report", "forward-test status"],
                "details": (
                    "Initialize a new 30-day forward testing validation cycle.\n"
                    "Forward testing validates trading strategy performance before "
                    "live deployment.\n\n"
                    "The test will:\n"
                    "  - Track all signals generated over 30 days\n"
                    "  - Monitor trade outcomes and P&L\n"
                    "  - Calculate performance metrics (Sharpe, win rate, drawdown)\n"
                    "  - Generate go/no-go recommendation after 30 days\n\n"
                    "Options:\n"
                    "  --capital AMOUNT    Starting capital for test (default: $10,000)"
                ),
            },
            "forward-test report": {
                "category": "Testing",
                "description": "Generate forward test reports",
                "usage": "forward-test report TEST_NAME [--type {daily|weekly|final}]",
                "examples": [
                    "forward-test report production_validation_2025",
                    "forward-test report my_test --type daily",
                    "forward-test report my_test --type weekly --week 2",
                ],
                "aliases": ["ftest report", "test report"],
                "tags": ["testing", "reporting"],
                "related": ["forward-test start", "forward-test status"],
                "details": (
                    "Generate performance reports for ongoing or completed forward tests.\n\n"
                    "Report Types:\n"
                    "  daily   - Daily summary of signals and trades\n"
                    "  weekly  - Week 1-4 performance breakdown\n"
                    "  final   - 30-day validation report with go/no-go recommendation\n\n"
                    "Reports include:\n"
                    "  - Sharpe ratio and risk-adjusted returns\n"
                    "  - Win rate and profit factor\n"
                    "  - Maximum drawdown\n"
                    "  - Trade-by-trade breakdown"
                ),
            },
            "forward-test status": {
                "category": "Testing",
                "description": "Show status of running forward tests",
                "usage": "forward-test status [TEST_NAME]",
                "examples": [
                    "forward-test status",
                    "forward-test status production_validation_2025",
                ],
                "aliases": ["ftest status", "test status"],
                "tags": ["testing", "status"],
                "related": ["forward-test start", "forward-test report"],
                "details": (
                    "Display status of active forward testing cycles.\n\n"
                    "Shows:\n"
                    "  - Days completed (X/30)\n"
                    "  - Number of signals generated\n"
                    "  - Open positions\n"
                    "  - Current P&L\n"
                    "  - Next milestone (week 1, 2, 3, 4, or final)\n\n"
                    "Without TEST_NAME, shows all active tests."
                ),
            },
            # ==================== CONFIGURATION COMMANDS (ENHANCED) ====================
            "show config-file": {
                "category": "Configuration",
                "description": "Show current configuration file settings",
                "usage": "show config-file [--file {trading|scanner|paths|market-hours}]",
                "examples": [
                    "show config-file",
                    "show config-file --file trading",
                    "show config-file --file scanner",
                ],
                "aliases": ["config-file", "show yaml"],
                "tags": ["configuration", "files", "issue-358"],
                "related": ["show config", "edit config"],
                "details": (
                    "Display contents of configuration YAML files (Issue #358).\n\n"
                    "Configuration Files:\n"
                    "  trading      - Strategy parameters (MACD, RSI, exits, timeframe)\n"
                    "  scanner      - Market scanner watchlist and settings\n"
                    "  paths        - File paths and directory structure\n"
                    "  market-hours - Market hours and holiday calendar\n\n"
                    "Without --file, shows summary of all config files.\n\n"
                    "Note: Config files are in config_defaults/ directory."
                ),
            },
            "set timeframe": {
                "category": "Configuration",
                "description": "Change trading timeframe",
                "usage": "set timeframe {1m|5m|15m|30m|1h|2h|4h|1d|1w|1M}",
                "examples": [
                    "set timeframe 1d",
                    "set timeframe 1h",
                    "set timeframe 15m",
                ],
                "aliases": ["timeframe"],
                "tags": ["configuration", "timeframe", "issue-365"],
                "related": ["show timeframe", "show config"],
                "details": (
                    "Change the timeframe for technical analysis (Issue #365).\n\n"
                    "Supported Timeframes:\n"
                    "  1m, 5m, 15m, 30m - Scalping/day trading\n"
                    "  1h, 2h, 4h        - Intraday swing trading\n"
                    "  1d                - Daily swing/position trading (validated default)\n"
                    "  1w, 1M            - Position/long-term trading\n\n"
                    "⚠️  Note: Only 1d timeframe has been validated (0.856 Sharpe).\n"
                    "   Other timeframes are experimental - use with caution.\n\n"
                    "Timeframe affects:\n"
                    "  - MACD and RSI calculations\n"
                    "  - Signal generation frequency\n"
                    "  - Stop loss and take profit levels"
                ),
            },
            "show indicators": {
                "category": "Configuration",
                "description": "List available technical indicators",
                "usage": "show indicators [--detailed]",
                "examples": [
                    "show indicators",
                    "show indicators --detailed",
                ],
                "aliases": ["indicators", "list indicators"],
                "tags": ["configuration", "indicators", "analysis"],
                "related": ["show config", "set voter-system"],
                "details": (
                    "Display all available technical indicators and their current parameters.\n\n"
                    "Current Indicators:\n"
                    "  MACD  - Moving Average Convergence Divergence (13/34/8)\n"
                    "  RSI   - Relative Strength Index (14, 30/70 levels)\n\n"
                    "Use --detailed to see full parameter descriptions and formulas.\n\n"
                    "Note: MACD uses Fibonacci parameters optimized across tech stocks."
                ),
            },
            "show watchlist": {
                "category": "Configuration",
                "description": "Show market scanner watchlist",
                "usage": "show watchlist [--category {etf|tech|all}]",
                "examples": [
                    "show watchlist",
                    "show watchlist --category tech",
                    "show watchlist --category etf",
                ],
                "aliases": ["watchlist", "symbols"],
                "tags": ["configuration", "scanner", "watchlist"],
                "related": ["show config-file", "morning-routine"],
                "details": (
                    "Display symbols in the market scanner watchlist.\n\n"
                    "Categories:\n"
                    "  etf  - Core ETFs (SPY, QQQ, IWM, VTI) + Leverage (TQQQ, SQQQ)\n"
                    "  tech - Tech giants (AAPL, MSFT, NVDA, TSLA, META, GOOGL, AMZN)\n"
                    "  all  - Complete watchlist (default)\n\n"
                    "Watchlist is configurable in config_defaults/scanner_config.yaml (Issue #358)."
                ),
            },
            # ==================== SCHEDULER COMMANDS ====================
            "show scheduler": {
                "category": "System",
                "description": "Show daily scheduler status",
                "usage": "show scheduler",
                "examples": [
                    "show scheduler",
                ],
                "aliases": ["scheduler", "scheduler status"],
                "tags": ["system", "scheduler", "automation"],
                "related": ["enable scheduler", "disable scheduler"],
                "details": (
                    "Display status of the daily automated scheduler.\n\n"
                    "Shows:\n"
                    "  - Scheduler state (enabled/disabled)\n"
                    "  - Next scheduled run (morning 9:20 AM ET or evening 3:50 PM ET)\n"
                    "  - Last run time and result\n"
                    "  - Configured tasks\n\n"
                    "The scheduler automates:\n"
                    "  - Morning market scan\n"
                    "  - Position monitoring\n"
                    "  - Stop loss adjustments\n"
                    "  - Evening summary reports"
                ),
            },
            "enable scheduler": {
                "category": "System",
                "description": "Enable daily automated scheduler",
                "usage": "enable scheduler",
                "examples": [
                    "enable scheduler",
                ],
                "aliases": ["scheduler on", "start scheduler"],
                "tags": ["system", "scheduler", "automation"],
                "related": ["disable scheduler", "show scheduler"],
                "details": (
                    "Enable the daily automated trading scheduler.\n\n"
                    "When enabled, the scheduler runs:\n"
                    "  Morning (9:20 AM ET):\n"
                    "    - Market scan for opportunities\n"
                    "    - Signal generation\n"
                    "    - Trade execution (if execution_mode = AUTO)\n\n"
                    "  Evening (3:50 PM ET):\n"
                    "    - Position review\n"
                    "    - Stop loss updates\n"
                    "    - Daily summary report\n\n"
                    "⚠️  Note: Scheduler respects your execution_mode setting."
                ),
            },
            "disable scheduler": {
                "category": "System",
                "description": "Disable daily automated scheduler",
                "usage": "disable scheduler",
                "examples": [
                    "disable scheduler",
                ],
                "aliases": ["scheduler off", "stop scheduler"],
                "tags": ["system", "scheduler"],
                "related": ["enable scheduler", "show scheduler"],
                "details": (
                    "Disable the daily automated scheduler.\n\n"
                    "Disabling the scheduler means:\n"
                    "  - No automatic morning scans\n"
                    "  - No automatic position monitoring\n"
                    "  - No automatic stop adjustments\n"
                    "  - You must run commands manually\n\n"
                    "Existing positions remain active - disabling scheduler doesn't close trades."
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

    def _get_similar_commands(self, command: str, max_suggestions: int = 3) -> List[str]:
        """
        Get similar command suggestions using fuzzy matching.

        Uses Levenshtein-like distance to find commands that might be typos.

        Args:
            command: User's input command
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of similar command names
        """

        def levenshtein_distance(s1: str, s2: str) -> int:
            """Calculate edit distance between two strings."""
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            if len(s2) == 0:
                return len(s1)

            previous_row = range(len(s2) + 1)
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row

            return previous_row[-1]

        # Calculate distances for all commands and aliases
        candidates = []
        command_lower = command.lower()

        for cmd, cmd_data in self.commands.items():
            distance = levenshtein_distance(command_lower, cmd.lower())
            # Only suggest if edit distance is reasonable (< 40% of command length)
            if distance <= max(2, len(command) * 0.4):
                candidates.append((cmd, distance))

            # Also check aliases
            aliases = cmd_data.get("aliases", [])
            for alias in aliases:
                distance = levenshtein_distance(command_lower, alias.lower())
                if distance <= max(2, len(command) * 0.4):
                    candidates.append((cmd, distance))

        # Sort by distance and return top suggestions
        candidates.sort(key=lambda x: x[1])
        suggestions = [cmd for cmd, _ in candidates[:max_suggestions]]

        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for cmd in suggestions:
            if cmd not in seen:
                seen.add(cmd)
                unique_suggestions.append(cmd)

        return unique_suggestions[:max_suggestions]

    def get_help_command(self, command: str) -> str:
        """Get detailed help for a specific command."""
        # Handle partial command names
        matching = [cmd for cmd in self.commands if cmd.startswith(command.lower())]

        if not matching:
            # Try to suggest similar commands
            suggestions = self._get_similar_commands(command)
            error_msg = f"❌ Command '{command}' not found."

            if suggestions:
                error_msg += "\n\n💡 Did you mean one of these?\n"
                for suggestion in suggestions:
                    desc = self.commands[suggestion].get("description", "")
                    error_msg += f"  - {suggestion:25} {desc}\n"
                error_msg += "\nType '/help COMMAND' to see details for any command."
            else:
                error_msg += " Type '/help' to see all commands."

            return error_msg

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
