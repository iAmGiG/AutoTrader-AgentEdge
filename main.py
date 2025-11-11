#!/usr/bin/env python3
"""
AutoGen-TradingSystem Main Runner
Unified entry point for all trading system operations.

Usage:
    python main.py --help                    # Show all commands
    python main.py test-voter                # Test current VoterAgent
    python main.py check-positions           # Check paper trading positions
    python main.py paper-trade <symbol>      # Run paper trading check and action
    python main.py analysis                  # Generate analysis reports
"""

import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import traceback

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import all trading system components at startup for efficiency
from src.autogen_agents.voter_agent import VoterAgent
from src.trading.trading_cycle import CostEfficientTradeCycle
from src.trading.alpaca_trading_client import AlpacaAccountMonitor, AlpacaOrderManager
from src.data_sources.tools import fetch_unified_market_data
from config_defaults.trading_config import TradingConfig


def test_voter_agent():
    """Test the current production VoterAgent."""
    print("🤖 Testing Production VoterAgent...")
    try:
        # Create VoterAgent with production parameters
        print("Creating VoterAgent with validated parameters...")
        voter = VoterAgent(
            name='production_voter',
            macd_params={'fast': 13, 'slow': 34, 'signal': 8},  # Validated Fibonacci parameters
            rsi_params={'period': 14, 'oversold': 30, 'overbought': 70},
            use_config_file=True
        )

        config = voter.get_current_configuration()
        print(f"✅ VoterAgent configured:")
        print(
            f"   MACD: ({config['macd']['fast']}/{config['macd']['slow']}/{config['macd']['signal']})")
        print(
            f"   RSI: {config['rsi']['period']} period, {config['rsi']['oversold']}/{config['rsi']['overbought']} levels")

        # Test with AAPL data
        print("\nFetching AAPL market data...")
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        market_data = fetch_unified_market_data("AAPL", start_date=start_date, end_date=end_date)

        if market_data is not None and not market_data.empty and len(market_data) >= 42:
            df = market_data
            if 'Close' not in df.columns and 'close' in df.columns:
                df['Close'] = df['close']

            print(f"✅ Loaded {len(df)} data points")
            print(f"   Price range: ${df['Close'].min():.2f} - ${df['Close'].max():.2f}")

            # Get trading decision
            result = voter.evaluate_voting('AAPL', df, return_components=True)

            print(f"\n📊 Trading Decision:")
            print(f"   Action: {result['action']} (Confidence: {result['confidence']:.1%})")
            print(f"   Reasoning: {result['reasoning']}")
            print(f"   Current Price: ${result.get('current_price', 0):.2f}")

            if 'components' in result:
                macd = result['components']['macd']
                rsi = result['components']['rsi']
                print(f"\n🔧 Component Analysis:")
                print(f"   MACD: {macd['action']} (Histogram: {macd['histogram']:.6f})")
                print(f"   RSI: {rsi['action']} (Value: {rsi['value']:.1f})")

            return True
        else:
            print("❌ Insufficient market data")
            return False

    except Exception as e:
        print(f"❌ Error testing VoterAgent: {e}")
        return False


def check_paper_positions():
    """Check current paper trading positions using existing tools."""
    print("📊 Checking Paper Trading Positions...")
    try:
        # Initialize account monitor
        monitor = AlpacaAccountMonitor(mode="paper")

        # Get comprehensive account status
        account = monitor.get_account_status()
        print(f"📈 Account Overview:")
        print(f"   Status: {account['status']}")
        print(f"   Buying Power: ${account['buying_power']:,.2f}")
        print(f"   Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"   Cash: ${account['cash']:,.2f}")

        # Get positions using the existing position manager
        positions = monitor.get_positions()
        if positions:
            print(f"\n📋 Current Positions ({len(positions)}):")
            total_value = 0
            for pos in positions:
                pnl = pos['unrealized_pl']
                pnl_pct = pos['unrealized_plpc'] * 100
                market_value = pos['market_value']
                total_value += market_value

                print(f"   {pos['symbol']}: {pos['qty']} shares @ ${pos['avg_entry_price']:.2f}")
                print(
                    f"     Market Value: ${market_value:,.2f} | P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")

            print(f"\n💰 Total Position Value: ${total_value:,.2f}")
        else:
            print("\n📋 No current positions")

        # Get recent orders
        recent_orders = monitor.get_orders(status='all', limit=5)
        if recent_orders:
            print(f"\n📋 Recent Orders ({len(recent_orders)}):")
            for order in recent_orders:
                print(
                    f"   {order['symbol']}: {order['side']} {order['qty']} @ {order['order_type']}")
                print(f"     Status: {order['status']}")
        else:
            print("\n📋 No recent orders")

        return True
    except Exception as e:
        print(f"❌ Error checking positions: {e}")
        print("💡 Make sure Alpaca API keys are configured in config/config.json")
        return False


def run_paper_trading_check(symbol: str = None):
    """Run comprehensive paper trading cycle and execute updates as needed."""
    print("🔄 Paper Trading System Check & Update")
    print("=" * 60)

    try:
        # Initialize trading infrastructure
        print("🔧 Initializing Trading Infrastructure...")
        cycle = CostEfficientTradeCycle()
        order_manager = AlpacaOrderManager(mode="paper")

        # Step 1: Fetch remote broker state (source of truth)
        print("\n1️⃣ Fetching Remote Broker State...")
        broker_state = cycle.fetch_broker_state()

        account = broker_state['account']
        print(f"   💰 Portfolio Value: ${account['portfolio_value']:,.2f}")
        print(f"   💵 Available Cash: ${account['cash']:,.2f}")
        print(f"   📊 Active Positions: {len(broker_state['positions'])}")
        print(f"   📋 Open Orders: {sum(len(orders) for orders in broker_state['orders'].values())}")

        # Step 2: Reconcile and update local state
        print("\n2️⃣ Reconciling Local vs Remote State...")
        discrepancies = cycle.reconcile_state(broker_state)

        if discrepancies:
            print(f"   🔄 Updating {len(discrepancies)} discrepancies:")
            for disc in discrepancies:
                severity_emoji = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}
                emoji = severity_emoji.get(disc.severity, '⚪')
                print(f"     {emoji} {disc.type}: {disc.symbol} - {disc.action}")
        else:
            print("   ✅ Local and remote states synchronized")

        # Step 2.5: Check for position alerts
        print("\n📊 Checking Position Alerts...")
        alerts = cycle.check_position_alerts(broker_state)

        if alerts:
            print(f"   🔔 {len(alerts)} Alert(s) Generated:")
            for alert in alerts:
                print(f"      {alert.message}")
        else:
            print("   ✅ No alerts - all positions within safe ranges")

        # Step 3: Review positions and execute stop updates
        print("\n3️⃣ Reviewing Positions and Executing Updates...")
        actions_taken = []

        if broker_state['positions']:
            stop_adjustments = cycle.calculate_stop_adjustments(broker_state)
            losing_positions = []

            # Execute stop adjustments for profitable positions
            if stop_adjustments:
                print(f"   🔄 Executing {len(stop_adjustments)} stop adjustments...")
                for adj in stop_adjustments:
                    try:
                        # Update stop order
                        success = order_manager.modify_stop_order(
                            order_id=adj.order_id,
                            new_stop_price=adj.new_stop,
                            symbol=adj.symbol
                        )

                        if success:
                            print(
                                f"     ✅ {adj.symbol}: Stop updated ${adj.current_stop:.2f} → ${adj.new_stop:.2f}")
                            print(f"        📝 {adj.reason}")
                            actions_taken.append(f"Updated stop for {adj.symbol}")
                        else:
                            print(f"     ❌ Failed to update stop for {adj.symbol}")

                    except Exception as e:
                        print(f"     ❌ Error updating stop for {adj.symbol}: {e}")

            # Review each position
            for pos_symbol, position in broker_state['positions'].items():
                print(f"\n   📈 {pos_symbol}:")
                print(f"      Quantity: {position['quantity']} shares")
                print(f"      Entry: ${position['entry_price']:.2f}")
                print(f"      Current: ${position['current_price']:.2f}")

                profit = position['current_price'] - position['entry_price']
                profit_pct = (profit / position['entry_price']) * 100
                print(f"      P&L: ${profit:+.2f} ({profit_pct:+.1f}%)")

                # Track losing positions for re-evaluation
                if profit_pct < -2.0:
                    losing_positions.append((pos_symbol, position, profit_pct))

            # Step 4: Re-evaluate losing positions and take action
            if losing_positions:
                print(f"\n4️⃣ Re-evaluating {len(losing_positions)} Losing Positions...")

                voter = VoterAgent(
                    name='position_reviewer',
                    macd_params={'fast': 13, 'slow': 34, 'signal': 8},
                    rsi_params={'period': 14, 'oversold': 30, 'overbought': 70},
                    use_config_file=True
                )

                for pos_symbol, position, loss_pct in losing_positions:
                    print(f"\n     🔍 Re-evaluating {pos_symbol} (Loss: {loss_pct:.1f}%)...")

                    try:
                        # Get fresh market data
                        end_date = datetime.now().strftime("%Y-%m-%d")
                        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
                        market_data = fetch_unified_market_data(
                            pos_symbol, start_date=start_date, end_date=end_date)
                        if market_data is not None and len(market_data) >= 42:
                            df = pd.DataFrame(market_data)
                            if 'Close' not in df.columns:
                                df['Close'] = df.get('close', df.get('c', 0))

                            # Get VoterAgent decision
                            decision = voter.evaluate_voting(pos_symbol, df)

                            print(f"       🤖 VoterAgent Decision: {decision['action']}")
                            print(f"       📝 Reasoning: {decision['reasoning']}")
                            print(f"       🎯 Confidence: {decision['confidence']:.1%}")

                            # Execute action based on VoterAgent decision
                            if decision['action'] == 'SELL' and decision['confidence'] > 0.6:
                                print(f"       🔴 EXECUTING: Exit position in {pos_symbol}")

                                try:
                                    # Close the position
                                    result = order_manager.close_position(pos_symbol)
                                    if result:
                                        print(f"       ✅ Position closed successfully")
                                        actions_taken.append(
                                            f"Closed losing position in {pos_symbol}")
                                    else:
                                        print(f"       ❌ Failed to close position")

                                except Exception as e:
                                    print(f"       ❌ Error closing position: {e}")

                            elif decision['action'] == 'HOLD' or decision['confidence'] < 0.6:
                                print(
                                    f"       🟡 HOLDING: Keeping position, insufficient confidence or hold signal")
                            else:
                                print(f"       🟢 HOLDING: VoterAgent suggests staying in position")

                        else:
                            print(f"       ❌ Insufficient data for re-evaluation")

                    except Exception as e:
                        print(f"       ❌ Error re-evaluating {pos_symbol}: {e}")

        else:
            print("   📭 No active positions to review")

        # Step 5: Update local state with all changes
        print("\n5️⃣ Updating Local State...")
        cycle.save_local_state()
        print("   💾 Local state synchronized with all updates")

        # Step 6: Summary of actions taken
        print(f"\n📊 Trading Cycle Summary:")
        print(f"   📈 Active Positions: {len(broker_state['positions'])}")
        print(
            f"   🔄 Stop Adjustments: {len(stop_adjustments) if 'stop_adjustments' in locals() else 0}")
        print(
            f"   📉 Losing Positions Reviewed: {len(losing_positions) if 'losing_positions' in locals() else 0}")
        print(f"   ⚠️  State Discrepancies Fixed: {len(discrepancies)}")
        print(f"   ✅ Actions Executed: {len(actions_taken)}")

        if actions_taken:
            print(f"\n🎯 Actions Taken This Cycle:")
            for i, action in enumerate(actions_taken, 1):
                print(f"   {i}. {action}")
        else:
            print(f"\n💤 No actions required this cycle")

        if symbol:
            # If specific symbol requested, provide focused analysis
            if symbol in broker_state['positions']:
                print(f"\n🎯 Focused Analysis: {symbol}")
                pos = broker_state['positions'][symbol]
                profit_pct = ((pos['current_price'] - pos['entry_price']) /
                              pos['entry_price']) * 100
                print(f"   Current P&L: {profit_pct:+.1f}%")
                print(
                    f"   Status: {'Needs attention' if abs(profit_pct) > 5 else 'Performing normally'}")
            else:
                print(f"\n🎯 No position found for {symbol}")

        print(f"\n✅ Paper trading cycle complete - System updated")
        return True

    except Exception as e:
        print(f"❌ Error in trading cycle: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_analysis():
    """Generate analysis reports."""
    print("📊 Generating Analysis Reports...")
    try:
        # Try to run analysis script
        from scripts.analysis.generate_results_summary import main as generate_summary
        generate_summary(['--advanced'])
        return True
    except Exception as e:
        print(f"❌ Error generating analysis: {e}")
        print("💡 Analysis scripts may need configuration")
        return False


def trade_assist():
    """Interactive CLI trading assistant."""
    import asyncio
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

    try:
        from cli import CLISession
        from core.factory import OrchestratorFactory

        print("\n🚀 Starting Trade Assistant (Production Mode)...")
        print("   - LLM Parser: gpt-4o-mini + o4-mini")
        print("   - Strategy: RealVoterAgent (MACD+RSI, 0.856 Sharpe)")
        print("   - Risk: SimpleRiskManager (portfolio % based)")
        print("   - Execution: AlpacaOrderManager (paper trading)")
        print()

        # Create orchestrator with real components
        factory = OrchestratorFactory()
        orchestrator = factory.create(
            order_manager=None,      # Auto-create from factory
            use_real_voter=True,     # Use production VoterAgent
            use_real_alpaca=True,    # Use real Alpaca OrderManager
            alpaca_mode="paper"      # Paper trading mode
        )

        # Create CLI session
        session = CLISession(orchestrator)

        # Run REPL
        asyncio.run(session.run())

        return True
    except Exception as e:
        print(f"❌ Error starting trade assistant: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AutoGen-TradingSystem Main Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py test-voter                    # Test production VoterAgent
  python main.py check-positions              # Check paper positions
  python main.py paper-trade AAPL             # Full trading check for AAPL
  python main.py analysis                     # Generate reports
  python main.py trade-assist                 # Interactive trading assistant (NEW)
        """
    )

    parser.add_argument('command', choices=[
        'test-voter', 'check-positions', 'paper-trade', 'analysis', 'trade-assist'
    ], help='Command to execute')

    parser.add_argument('symbol', nargs='?', default='AAPL',
                        help='Stock symbol (for paper-trade command)')

    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

    print("AutoGen-TradingSystem")
    print("=" * 30)
    print(f"Command: {args.command}")
    if args.command == 'paper-trade':
        print(f"Symbol: {args.symbol}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 30)

    try:
        if args.command == 'test-voter':
            success = test_voter_agent()
        elif args.command == 'check-positions':
            success = check_paper_positions()
        elif args.command == 'paper-trade':
            success = run_paper_trading_check(args.symbol)
        elif args.command == 'analysis':
            success = generate_analysis()
        elif args.command == 'trade-assist':
            success = trade_assist()
        else:
            print(f"❌ Unknown command: {args.command}")
            success = False

        if success:
            print(f"\n✅ '{args.command}' completed successfully")
        else:
            print(f"\n❌ '{args.command}' failed")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
