#!/usr/bin/env python3
"""
AutoGen-TradingSystem Main Runner
Unified entry point for all trading system operations.

Usage:
    python main.py                           # Launch interactive trading assistant
    python main.py --help                    # Show all commands
    python main.py --daemon                  # Run automated scheduler

In CLI, use natural language for trading modes:
    > buy SPY aggressively
    > I want to be conservative with this AAPL trade
    > set risk mode to moderate
"""

import argparse
import asyncio
import os
import sys
import traceback
from datetime import timedelta

import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import all trading system components at startup for efficiency
from src.autogen_agents.voter_agent import VoterAgent
from src.data_sources.tools import fetch_unified_market_data
from src.trading.account_manager import get_account_manager
from src.trading.alpaca_trading_client import AlpacaAccountMonitor, AlpacaOrderManager
from src.trading.daily_scheduler import DailyScheduler
from src.trading.trading_cycle import CostEfficientTradeCycle
from src.utils.date_utils import get_datetime_now
from src.utils.safe_print import get_severity_symbol, get_symbol, safe_print

try:
    from scripts.research.v0_v4_analysis.generate_results_summary import (
        main as generate_summary,
    )
except ImportError:
    generate_summary = None

# CLI imports (may not be available in all environments)
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
    from cli import CLISession
    from core.factory import OrchestratorFactory
    from core.trading_modes import get_mode_manager

    CLI_AVAILABLE = True
except ImportError:
    CLI_AVAILABLE = False
    CLISession = None
    OrchestratorFactory = None
    get_mode_manager = None


def test_voter_agent():
    """Test the current production VoterAgent."""
    safe_print(f"{get_symbol('ROBOT')} Testing Production VoterAgent...")
    try:
        # Create VoterAgent with production parameters
        print("Creating VoterAgent with validated parameters...")
        voter = VoterAgent(
            name="production_voter",
            macd_params={"fast": 13, "slow": 34, "signal": 8},  # Validated Fibonacci parameters
            rsi_params={"period": 14, "oversold": 30, "overbought": 70},
            use_config_file=True,
        )

        config = voter.get_current_configuration()
        safe_print(f"{get_symbol('SUCCESS')} VoterAgent configured:")
        print(
            f"   MACD: ({config['macd']['fast']}/{config['macd']['slow']}/{config['macd']['signal']})"
        )
        print(
            f"   RSI: {config['rsi']['period']} period, {config['rsi']['oversold']}/{config['rsi']['overbought']} levels"
        )

        # Test with AAPL data
        print("\nFetching AAPL market data...")
        end_date = get_datetime_now().strftime("%Y-%m-%d")
        start_date = (get_datetime_now() - timedelta(days=60)).strftime("%Y-%m-%d")
        market_data = fetch_unified_market_data("AAPL", start_date=start_date, end_date=end_date)

        if market_data is not None and not market_data.empty and len(market_data) >= 42:
            df = market_data
            if "Close" not in df.columns and "close" in df.columns:
                df["Close"] = df["close"]

            safe_print(f"{get_symbol('SUCCESS')} Loaded {len(df)} data points")
            print(f"   Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")

            # Get trading decision
            result = voter.evaluate_voting("AAPL", df, return_components=True)

            safe_print(f"\n{get_symbol('INFO')} Trading Decision:")
            print(f"   Action: {result['action']} (Confidence: {result['confidence']:.1%})")
            print(f"   Reasoning: {result['reasoning']}")
            print(f"   Current Price: ${result.get('current_price', 0):.2f}")

            if "components" in result:
                macd = result["components"]["macd"]
                rsi = result["components"]["rsi"]
                safe_print(f"\n{get_symbol('GEAR')} Component Analysis:")
                print(f"   MACD: {macd['action']} (Histogram: {macd['histogram']:.6f})")
                print(f"   RSI: {rsi['action']} (Value: {rsi['value']:.1f})")

            return True
        else:
            safe_print(f"{get_symbol('ERROR')} Insufficient market data")
            return False

    except (ValueError, KeyError, RuntimeError) as e:
        safe_print(f"{get_symbol('ERROR')} Error testing VoterAgent: {e}")
        return False


def check_paper_positions():
    """Check current paper trading positions using existing tools."""
    safe_print(f"{get_symbol('INFO')} Checking Paper Trading Positions...")
    try:
        # Initialize account monitor
        monitor = AlpacaAccountMonitor(mode="paper")

        # Get comprehensive account status
        account = monitor.get_account_status()
        safe_print(f"{get_symbol('CHART')} Account Overview:")
        print(f"   Status: {account['status']}")
        print(f"   Buying Power: ${account['buying_power']:,.2f}")
        print(f"   Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"   Cash: ${account['cash']:,.2f}")

        # Get positions using the existing position manager
        positions = monitor.get_positions()
        if positions:
            print(f"\n[POSITIONS] Current Positions ({len(positions)}):")
            total_value = 0
            for pos in positions:
                pnl = pos["unrealized_pl"]
                pnl_pct = pos["unrealized_plpc"] * 100
                market_value = pos["market_value"]
                total_value += market_value

                print(f"   {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f}")
                print(
                    f"     Market Value: ${market_value:,.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)"
                )

            print(f"\n[TOTAL] Total Position Value: ${total_value:,.2f}")
        else:
            print("\n[POSITIONS] No current positions")

        # Get recent orders
        recent_orders = monitor.get_orders(status="all", limit=5)
        if recent_orders:
            print(f"\n[ORDERS] Recent Orders ({len(recent_orders)}):")
            for order in recent_orders:
                print(
                    f"   {order['symbol']}: {order['side']} {order['qty']} @ {order['order_type']}"
                )
                print(f"     Status: {order['status']}")
        else:
            print("\n[ORDERS] No recent orders")

        return True
    except (ValueError, KeyError, RuntimeError, ConnectionError) as e:
        safe_print(f"{get_symbol('ERROR')} Error checking positions: {e}")
        safe_print(
            f"{get_symbol('INFO')} Make sure Alpaca API keys are configured in config/config.json"
        )
        return False


def run_paper_trading_check(symbol: str = None):
    """Run comprehensive paper trading cycle and execute updates as needed."""
    safe_print(f"{get_symbol('CYCLE')} Paper Trading System Check & Update")
    print("=" * 60)

    try:
        # Initialize trading infrastructure
        safe_print(f"{get_symbol('GEAR')} Initializing Trading Infrastructure...")
        cycle = CostEfficientTradeCycle()
        order_manager = AlpacaOrderManager(mode="paper")

        # Step 1: Fetch remote broker state (source of truth)
        print("\n1️⃣ Fetching Remote Broker State...")
        broker_state = cycle.fetch_broker_state()

        account = broker_state["account"]
        print(f"   [VALUE] Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"   [CASH] Available Cash: ${account['cash']:,.2f}")
        print(f"   [POSITIONS] Active Positions: {len(broker_state['positions'])}")
        print(
            f"   [ORDERS] Open Orders: {sum(len(orders) for orders in broker_state['orders'].values())}"
        )

        # Step 2: Reconcile and update local state
        print("\n2️⃣ Reconciling Local vs Remote State...")
        discrepancies = cycle.reconcile_state(broker_state)

        if discrepancies:
            safe_print(f"   {get_symbol('CYCLE')} Updating {len(discrepancies)} discrepancies:")
            for disc in discrepancies:
                emoji = get_severity_symbol(disc.severity)
                print(f"     {emoji} {disc.type}: {disc.symbol} - {disc.action}")
        else:
            safe_print(f"   {get_symbol('SUCCESS')} Local and remote states synchronized")

        # Step 2.5: Check for position alerts
        safe_print(f"\n{get_symbol('INFO')} Checking Position Alerts...")
        alerts = cycle.check_position_alerts(broker_state)

        if alerts:
            safe_print(f"   {get_symbol('BELL')} {len(alerts)} Alert(s) Generated:")
            for alert in alerts:
                print(f"      {alert.message}")
        else:
            safe_print(f"   {get_symbol('SUCCESS')} No alerts - all positions within safe ranges")

        # Step 3: Review positions and execute stop updates
        print("\n3️⃣ Reviewing Positions and Executing Updates...")
        actions_taken = []

        if broker_state["positions"]:
            stop_adjustments = cycle.calculate_stop_adjustments(broker_state)
            losing_positions = []

            # Execute stop adjustments for profitable positions
            if stop_adjustments:
                safe_print(
                    f"   {get_symbol('CYCLE')} Executing {len(stop_adjustments)} stop adjustments..."
                )
                for adj in stop_adjustments:
                    try:
                        # Update stop order
                        # pylint: disable=no-member  # AlpacaOrderManager has this method
                        success = order_manager.modify_stop_order(
                            order_id=adj.order_id, new_stop_price=adj.new_stop, symbol=adj.symbol
                        )

                        if success:
                            safe_print(
                                f"     {get_symbol('SUCCESS')} {adj.symbol}: Stop updated ${adj.current_stop:.2f} → ${adj.new_stop:.2f}"
                            )
                            print(f"        [NOTE] {adj.reason}")
                            actions_taken.append(f"Updated stop for {adj.symbol}")
                        else:
                            safe_print(
                                f"     {get_symbol('ERROR')} Failed to update stop for {adj.symbol}"
                            )

                    except (ValueError, KeyError, RuntimeError, ConnectionError) as e:
                        safe_print(
                            f"     {get_symbol('ERROR')} Error updating stop for {adj.symbol}: {e}"
                        )

            # Review each position
            for pos_symbol, position in broker_state["positions"].items():
                safe_print(f"\n   {get_symbol('CHART')} {pos_symbol}:")
                print(f"      Quantity: {position['quantity']} shares")
                print(f"      Entry: ${position['entry_price']:.2f}")
                print(f"      Current: ${position['current_price']:.2f}")

                profit = position["current_price"] - position["entry_price"]
                profit_pct = (profit / position["entry_price"]) * 100
                print(f"      P&L: ${profit:+.2f} ({profit_pct:+.1f}%)")

                # Track losing positions for re-evaluation
                if profit_pct < -2.0:
                    losing_positions.append((pos_symbol, position, profit_pct))

            # Step 4: Re-evaluate losing positions and take action
            if losing_positions:
                print(f"\n4️⃣ Re-evaluating {len(losing_positions)} Losing Positions...")

                voter = VoterAgent(
                    name="position_reviewer",
                    macd_params={"fast": 13, "slow": 34, "signal": 8},
                    rsi_params={"period": 14, "oversold": 30, "overbought": 70},
                    use_config_file=True,
                )

                for pos_symbol, position, loss_pct in losing_positions:
                    print(f"\n     [EVAL] Re-evaluating {pos_symbol} (Loss: {loss_pct:.1f}%)...")

                    try:
                        # Get fresh market data
                        end_date = get_datetime_now().strftime("%Y-%m-%d")
                        start_date = (get_datetime_now() - timedelta(days=60)).strftime("%Y-%m-%d")
                        market_data = fetch_unified_market_data(
                            pos_symbol, start_date=start_date, end_date=end_date
                        )
                        if market_data is not None and len(market_data) >= 42:
                            df = pd.DataFrame(market_data)
                            if "Close" not in df.columns:
                                df["Close"] = df.get("close", df.get("c", 0))

                            # Get VoterAgent decision
                            decision = voter.evaluate_voting(pos_symbol, df)

                            safe_print(
                                f"       {get_symbol('ROBOT')} VoterAgent Decision: {decision['action']}"
                            )
                            print(f"       [REASON] Reasoning: {decision['reasoning']}")
                            safe_print(
                                f"       {get_symbol('TARGET')} Confidence: {decision['confidence']:.1%}"
                            )

                            # Execute action based on VoterAgent decision
                            if decision["action"] == "SELL" and decision["confidence"] > 0.6:
                                safe_print(
                                    f"       {get_symbol('EXECUTE')} EXECUTING: Exit position in {pos_symbol}"
                                )

                                try:
                                    # Close the position
                                    result = order_manager.close_position(pos_symbol)
                                    if result:
                                        safe_print(
                                            f"       {get_symbol('SUCCESS')} Position closed successfully"
                                        )
                                        actions_taken.append(
                                            f"Closed losing position in {pos_symbol}"
                                        )
                                    else:
                                        safe_print(
                                            f"       {get_symbol('ERROR')} Failed to close position"
                                        )

                                except (ValueError, KeyError, RuntimeError, ConnectionError) as e:
                                    safe_print(
                                        f"       {get_symbol('ERROR')} Error closing position: {e}"
                                    )

                            elif decision["action"] == "HOLD" or decision["confidence"] < 0.6:
                                safe_print(
                                    f"       {get_symbol('HOLD')} HOLDING: Keeping position, insufficient confidence or hold signal"
                                )
                            else:
                                safe_print(
                                    f"       {get_symbol('WAIT')} HOLDING: VoterAgent suggests staying in position"
                                )

                        else:
                            safe_print(
                                f"       {get_symbol('ERROR')} Insufficient data for re-evaluation"
                            )

                    except (ValueError, KeyError, RuntimeError, ConnectionError) as e:
                        safe_print(
                            f"       {get_symbol('ERROR')} Error re-evaluating {pos_symbol}: {e}"
                        )

        else:
            safe_print(f"   {get_symbol('MAILBOX')} No active positions to review")

        # Step 5: Update local state with all changes
        print("\n5️⃣ Updating Local State...")
        cycle.save_local_state()
        safe_print(f"   {get_symbol('SAVE')} Local state synchronized with all updates")

        # Step 6: Summary of actions taken
        safe_print(f"\n{get_symbol('INFO')} Trading Cycle Summary:")
        safe_print(f"   {get_symbol('CHART')} Active Positions: {len(broker_state['positions'])}")
        safe_print(
            f"   {get_symbol('CYCLE')} Stop Adjustments: {len(stop_adjustments) if 'stop_adjustments' in locals() else 0}"
        )
        print(
            f"   [REVIEW] Losing Positions Reviewed: {len(losing_positions) if 'losing_positions' in locals() else 0}"
        )
        safe_print(f"   {get_symbol('WARNING')} State Discrepancies Fixed: {len(discrepancies)}")
        safe_print(f"   {get_symbol('SUCCESS')} Actions Executed: {len(actions_taken)}")

        if actions_taken:
            safe_print(f"\n{get_symbol('TARGET')} Actions Taken This Cycle:")
            for i, action in enumerate(actions_taken, 1):
                print(f"   {i}. {action}")
        else:
            safe_print(f"\n{get_symbol('SLEEP')} No actions required this cycle")

        if symbol:
            # If specific symbol requested, provide focused analysis
            if symbol in broker_state["positions"]:
                safe_print(f"\n{get_symbol('TARGET')} Focused Analysis: {symbol}")
                pos = broker_state["positions"][symbol]
                profit_pct = (
                    (pos["current_price"] - pos["entry_price"]) / pos["entry_price"]
                ) * 100
                print(f"   Current P&L: {profit_pct:+.1f}%")
                print(
                    f"   Status: {'Needs attention' if abs(profit_pct) > 5 else 'Performing normally'}"
                )
            else:
                safe_print(f"\n{get_symbol('TARGET')} No position found for {symbol}")

        safe_print(f"\n{get_symbol('SUCCESS')} Paper trading cycle complete - System updated")
        return True

    except (ValueError, KeyError, RuntimeError, ConnectionError) as e:
        safe_print(f"{get_symbol('ERROR')} Error in trading cycle: {e}")
        traceback.print_exc()
        return False


def generate_analysis():
    """Generate analysis reports."""
    safe_print(f"{get_symbol('INFO')} Generating Analysis Reports...")
    try:
        # Try to run analysis script
        if generate_summary is None:
            raise ImportError("Analysis script not available")

        # Save original sys.argv and temporarily set it for argparse
        original_argv = sys.argv
        sys.argv = ["generate_results_summary.py", "--advanced"]
        try:
            generate_summary()
        finally:
            sys.argv = original_argv
        return True
    except (ImportError, ValueError, RuntimeError) as e:
        safe_print(f"{get_symbol('ERROR')} Error generating analysis: {e}")
        safe_print(f"{get_symbol('INFO')} Analysis scripts may need configuration")
        return False


def list_accounts():
    """
    List all configured trading accounts.

    Issue #401: Multi-account portfolio management.
    """
    safe_print(f"{get_symbol('INFO')} Configured Trading Accounts:")
    print("=" * 60)

    manager = get_account_manager()

    # Discover all accounts (query Alpaca API for details)
    safe_print(f"{get_symbol('GEAR')} Discovering account details...")
    manager.discover_all_accounts()

    accounts = manager.list_accounts()

    if not accounts:
        safe_print(f"{get_symbol('WARNING')} No accounts configured.")
        print("\nTo add accounts, update config/config.json with:")
        print('  "accounts": [')
        print('    {"id": "paper_main", "api_key": "...", "api_secret": "...", "alias": "Paper"}')
        print("  ]")
        return False

    for acc in accounts:
        status_icon = get_symbol("SUCCESS") if acc.get("has_info") else get_symbol("WARNING")
        active_tag = " [ACTIVE]" if acc.get("is_active") else ""
        enabled_tag = "" if acc.get("enabled", True) else " [DISABLED]"

        print(f"\n{status_icon} {acc['id']}{active_tag}{enabled_tag}")

        if acc.get("alias"):
            print(f"   Alias: {acc['alias']}")

        if acc.get("has_info"):
            acc_type = acc.get("account_type", "unknown").upper()
            print(f"   Type: {acc_type}")
            print(f"   Account #: {acc.get('account_number', 'N/A')}")
            print(f"   Portfolio: ${acc.get('portfolio_value', 0):,.2f}")
            print(f"   Buying Power: ${acc.get('buying_power', 0):,.2f}")
            print(f"   Status: {acc.get('status', 'Unknown')}")
        else:
            error = acc.get("last_error", "Discovery pending")
            print(f"   Status: Not discovered ({error})")

    print("\n" + "=" * 60)
    print(f"Total: {len(accounts)} account(s) configured")
    print("\nUsage: python main.py --account <ACCOUNT_ID>")
    return True


def trade_assist(account_id: str = None):
    """Interactive CLI trading assistant.

    Trading modes can be set via natural language:
        > buy SPY aggressively
        > set risk mode to conservative
        > I want to be careful with this trade

    Args:
        account_id: Optional account ID to use (#401)
    """
    if not CLI_AVAILABLE:
        safe_print(f"{get_symbol('ERROR')} CLI components not available")
        sys.exit(1)

    try:
        # Multi-account setup (#401)
        alpaca_mode = "paper"  # Default
        active_account_info = None

        if account_id:
            manager = get_account_manager()

            # Try to set the requested account as active
            if manager.set_active_account(account_id):
                active_account = manager.get_active_account()
                if active_account and active_account.info:
                    active_account_info = active_account.info
                    alpaca_mode = active_account_info.account_type.value
                    safe_print(
                        f"{get_symbol('SUCCESS')} Using account: {account_id} "
                        f"({alpaca_mode.upper()})"
                    )
            else:
                safe_print(f"{get_symbol('ERROR')} Account '{account_id}' not found or not ready")
                safe_print(f"{get_symbol('INFO')} Use --list-accounts to see available accounts")
                return False

        # Get default mode info for display
        mode_manager = get_mode_manager()
        mode_params = mode_manager.get_parameters()

        safe_print(f"\n{get_symbol('ROCKET')} Starting Trade Assistant (Production Mode)...")
        print(
            f"   - Default Mode: {mode_params.mode.value} (say 'aggressive' or 'conservative' to change)"
        )
        print("   - LLM Parser: gpt-4o-mini")
        print("   - Strategy: RealVoterAgent (MACD+RSI, 0.856 Sharpe)")

        if active_account_info:
            print(f"   - Account: {active_account_info.alias or account_id} ({alpaca_mode})")
            print(f"   - Portfolio: ${active_account_info.portfolio_value:,.2f}")
        else:
            print(f"   - Execution: AlpacaOrderManager ({alpaca_mode} trading)")
        print()

        # Create orchestrator with real components
        factory = OrchestratorFactory()
        orchestrator = factory.create(
            order_manager=None,  # Auto-create from factory
            use_real_voter=True,  # Use production VoterAgent
            use_real_alpaca=True,  # Use real Alpaca OrderManager
            alpaca_mode=alpaca_mode,  # Use detected mode from account
        )

        # Create CLI session
        session = CLISession(orchestrator)

        # Run REPL
        asyncio.run(session.run())

        return True
    except (ImportError, ValueError, RuntimeError) as e:
        safe_print(f"{get_symbol('ERROR')} Error starting trade assistant: {e}")
        traceback.print_exc()
        return False


def main():
    """
    Main entry point - Unified Interactive CLI.

    Default: Launches interactive trading assistant
    --daemon: Runs scheduler in background
    --legacy: Access legacy one-shot commands
    """
    parser = argparse.ArgumentParser(
        description="AutoGen Trading System - Production-Ready Multi-Agent Trading Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
╔════════════════════════════════════════════════════════════════╗
║                    AUTOGEN-TRADER CLI v2.0                      ║
║     Production-Ready MACD+RSI Voting (0.856 Sharpe Ratio)      ║
╚════════════════════════════════════════════════════════════════╝

QUICK START:
  python main.py                     # Launch interactive trading assistant
  python main.py --daemon            # Run automated scheduler (background)
  python main.py --list-accounts     # List configured trading accounts (#401)
  python main.py --account paper     # Use specific account (#401)
  python main.py --help              # Show this help

INTERACTIVE CLI COMMANDS (type /help for full list):

  Trading (with natural language risk modes - Issue #400):
    > buy AAPL 10                    # Buy 10 shares (default: moderate risk)
    > buy SPY aggressively           # Buy with aggressive position sizing
    > conservative buy MSFT 5        # Buy with conservative risk settings
    > sell TSLA, be aggressive       # Sell with larger position
    > show positions                 # View open positions
    > show portfolio                 # Portfolio summary

  Risk Modes (adjustable mid-session):
    > set risk mode to conservative  # 5% max position, 2% stop loss
    > I want to be aggressive        # 20% max position, 8% stop loss
    > what's my current risk mode?   # Show active mode settings

  Workflows:
    > morning-routine                # Run morning market scan
    > monitor                        # Monitor positions for exit signals
    > evening-summary                # Generate end-of-day report

  Configuration (Issue #358, #365):
    > show config-file               # View YAML config files
    > show timeframe                 # Show current timeframe (1d default)
    > set timeframe 1h               # Change to hourly timeframe
    > show watchlist                 # View scanner watchlist

  Forward Testing (Issue #324):
    > forward-test start TEST_NAME   # Start 30-day validation test
    > forward-test report TEST_NAME  # Generate test report
    > forward-test status            # Check test progress

  Scheduler & Automation:
    > show scheduler                 # View scheduler status
    > enable scheduler               # Enable automated trading
    > disable scheduler              # Disable automation

  Help:
    > /help                          # Show all commands
    > /help COMMAND                  # Detailed help for command
    > /help search KEYWORD           # Search commands
    > /exit                          # Exit CLI

FEATURES:
  - VoterAgent (MACD+RSI) - 0.856 Sharpe, production-validated
  - Trading Modes - Conservative/Moderate/Aggressive via natural language
  - Configuration System - YAML-based strategy parameters
  - Timeframe Support - Trade on 1m to 1M timeframes
  - Forward Testing - 30-day validation protocol
  - Daily Scheduler - Automated morning/evening routines
  - Risk Management - Portfolio limits & position sizing
  - Paper Trading - Test strategies without real money
  - Multi-Account (#401) - Manage multiple trading accounts

LEGACY COMMANDS (deprecated, use interactive CLI instead):
  python main.py --legacy test-voter           # Test VoterAgent
  python main.py --legacy check-positions      # Check positions
  python main.py --legacy paper-trade SYMBOL   # Paper trade symbol
  python main.py --legacy analysis             # Generate reports
        """,
    )

    parser.add_argument(
        "--daemon", action="store_true", help="Run daily scheduler in background (daemon mode)"
    )

    parser.add_argument(
        "--legacy", nargs="+", metavar="COMMAND", help="Run legacy one-shot command (deprecated)"
    )

    # Multi-account support (#401)
    parser.add_argument(
        "--account",
        "-a",
        type=str,
        metavar="ACCOUNT_ID",
        help="Select trading account (e.g., --account paper_main)",
    )

    parser.add_argument(
        "--list-accounts",
        action="store_true",
        help="List all configured trading accounts",
    )

    # If no arguments, launch interactive CLI
    if len(sys.argv) == 1:
        safe_print(f"{get_symbol('ROCKET')} Launching Interactive Trading Assistant...")
        print("   (Use --help to see all options)")
        print()
        try:
            success = trade_assist()
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            safe_print(f"\n{get_symbol('STOP')} Cancelled by user")
            sys.exit(0)
        except (ImportError, ValueError, RuntimeError) as e:
            safe_print(f"\n{get_symbol('EXPLOSION')} Error: {e}")
            sys.exit(1)

    args = parser.parse_args()

    # List accounts mode (#401)
    if args.list_accounts:
        try:
            success = list_accounts()
            sys.exit(0 if success else 1)
        except (ImportError, ValueError, RuntimeError) as e:
            safe_print(f"{get_symbol('ERROR')} Error listing accounts: {e}")
            sys.exit(1)

    # Account selection with interactive CLI (#401)
    if args.account and not args.legacy and not args.daemon:
        safe_print(
            f"{get_symbol('ROCKET')} Launching Trading Assistant with account: {args.account}"
        )
        print()
        try:
            success = trade_assist(account_id=args.account)
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            safe_print(f"\n{get_symbol('STOP')} Cancelled by user")
            sys.exit(0)
        except (ImportError, ValueError, RuntimeError) as e:
            safe_print(f"\n{get_symbol('EXPLOSION')} Error: {e}")
            sys.exit(1)

    # Daemon mode - run scheduler
    if args.daemon:
        safe_print(f"{get_symbol('ROBOT')} Starting Daily Scheduler Daemon...")
        print("   Press Ctrl+C to stop")
        print()
        try:
            scheduler = DailyScheduler()
            asyncio.run(scheduler.run_daemon(check_interval_seconds=60))
            sys.exit(0)
        except KeyboardInterrupt:
            safe_print(f"\n{get_symbol('STOP')} Scheduler stopped by user")
            sys.exit(0)
        except (ImportError, ValueError, RuntimeError) as e:
            safe_print(f"\n{get_symbol('EXPLOSION')} Scheduler error: {e}")
            sys.exit(1)

    # Legacy mode - one-shot commands (deprecated)
    if args.legacy:
        command = args.legacy[0]
        symbol = args.legacy[1] if len(args.legacy) > 1 else "AAPL"

        safe_print(
            f"{get_symbol('WARNING')} DEPRECATED: Legacy commands will be removed in future version"
        )
        print("   Please use interactive CLI instead (python main.py)")
        print()
        print("AutoGen-TradingSystem")
        print("=" * 30)
        print(f"Command: {command}")
        if command == "paper-trade":
            print(f"Symbol: {symbol}")
        print(f"Time: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 30)

        try:
            if command == "test-voter":
                success = test_voter_agent()
            elif command == "check-positions":
                success = check_paper_positions()
            elif command == "paper-trade":
                success = run_paper_trading_check(symbol)
            elif command == "analysis":
                success = generate_analysis()
            elif command == "trade-assist":
                success = trade_assist()
            else:
                safe_print(f"{get_symbol('ERROR')} Unknown command: {command}")
                print("Available: test-voter, check-positions, paper-trade, analysis, trade-assist")
                success = False

            if success:
                safe_print(f"\n{get_symbol('SUCCESS')} '{command}' completed successfully")
            else:
                safe_print(f"\n{get_symbol('ERROR')} '{command}' failed")
                sys.exit(1)

        except KeyboardInterrupt:
            safe_print(f"\n{get_symbol('STOP')} Cancelled by user")
            sys.exit(1)
        except (ImportError, ValueError, RuntimeError) as e:
            safe_print(f"\n{get_symbol('EXPLOSION')} Error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
