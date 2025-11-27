#!/usr/bin/env python3
"""
CLI Interface - Command-line interface for human trading decisions
Part of RH2MAS AutoGen trading system
"""

import argparse
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.autogen_agents.orchestrator import create_trading_orchestrator
from src.human_interface.decision_formatter import DecisionFormatter


class TradingCLI:
    """
    Command-line interface for interacting with the RH2MAS trading system.
    Provides human-friendly commands for market analysis and trade execution.
    """

    def __init__(self, initial_capital: float = 100000):
        self.orchestrator = create_trading_orchestrator(initial_capital)
        self.formatter = DecisionFormatter()

    def scan_market(
        self, symbols: Optional[List[str]] = None, execute_approved: bool = False
    ) -> None:
        """
        Scan market and present trading opportunities.

        Args:
            symbols: Symbols to scan
            execute_approved: Whether to prompt for trade execution
        """
        print("\n🔍 MARKET SCAN INITIATED")
        print("=" * 50)

        try:
            # Run comprehensive analysis
            results = self.orchestrator.scan_and_analyze(symbols)

            # Display scan summary
            scan_count = len(results["scan_results"])
            signal_count = sum(
                1
                for r in results["trading_recommendations"].values()
                if r.get("decision", "").startswith("ENTER")
            )
            validated_count = len(results["validated_trades"])

            print(f"📊 Scanned {scan_count} symbols")
            print(f"🎯 Found {signal_count} trading signals")
            print(f"✅ {validated_count} passed risk validation")

            # Show validated trading opportunities
            if results["validated_trades"]:
                print("\n" + "=" * 60)
                print("TRADING OPPORTUNITIES:")
                print("=" * 60)

                decision_prompt = self.orchestrator.create_human_decision_prompt(results)
                print(decision_prompt)

                if execute_approved:
                    self._prompt_for_executions(results["validated_trades"])
            else:
                print("\n⚪ No trading opportunities at current risk thresholds")

            # Account summary
            print(f"\n{self.orchestrator.generate_trading_report()}")

        except Exception as e:
            print(f"❌ Scan failed: {e}")

    def monitor_positions(self) -> None:
        """Monitor existing positions for exit signals."""
        print("\n📈 POSITION MONITORING")
        print("=" * 50)

        try:
            monitoring_results = self.orchestrator.monitor_positions()

            # Show automatic exits
            auto_exits = monitoring_results.get("automatic_exits", [])
            if auto_exits:
                print("⚡ AUTOMATIC EXITS TRIGGERED:")
                for exit_info in auto_exits:
                    symbol = exit_info.get("symbol", "Unknown")
                    reason = exit_info.get("reason", "Unknown")
                    pnl = exit_info.get("realized_pnl", 0)
                    print(f"  {symbol}: {reason} → ${pnl:+,.2f}")

            # Show exit recommendations
            exit_recs = monitoring_results.get("exit_recommendations", {})
            if exit_recs:
                print("\n🎯 EXIT SIGNAL ANALYSIS:")
                for symbol, rec in exit_recs.items():
                    decision = rec.get("decision", "HOLD")
                    reason = rec.get("reason", "")
                    print(f"  {symbol}: {decision}")
                    if reason:
                        print(f"    Reason: {reason}")

            # Account update
            account_status = monitoring_results.get("account_status", {})
            if account_status:
                total_value = account_status.get("total_value", 0)
                unrealized_pnl = account_status.get("unrealized_pnl", 0)
                print(f"\n💰 Account: ${total_value:,.2f} (${unrealized_pnl:+,.2f} unrealized)")

        except Exception as e:
            print(f"❌ Position monitoring failed: {e}")

    def show_status(self) -> None:
        """Display comprehensive trading system status."""
        print(f"\n{self.orchestrator.generate_trading_report()}")

    def close_position(self, symbol: str) -> None:
        """
        Manually close a position.

        Args:
            symbol: Symbol to close
        """
        print(f"\n🔄 CLOSING POSITION: {symbol}")
        print("=" * 30)

        try:
            # Get current price from scanner
            market_data = self.orchestrator.scanner_agent.get_market_data(symbol)
            if not market_data or "current_price" in market_data:
                print(f"❌ Unable to get current price for {symbol}")
                return

            current_price = market_data["current_price"]

            # Close position
            result = self.orchestrator.executor_agent.close_position(
                symbol, current_price, "MANUAL_CLOSE"
            )

            if result["status"] == "CLOSED":
                pnl = result.get("realized_pnl", 0)
                print(f"✅ Position closed: {symbol}")
                print(f"   Realized P&L: ${pnl:+,.2f}")
            elif result["status"] == "NOT_FOUND":
                print(f"❌ No open position found for {symbol}")
            else:
                print(f"❌ Close failed: {result.get('reason', 'Unknown error')}")

        except Exception as e:
            print(f"❌ Error closing position: {e}")

    def _prompt_for_executions(self, validated_trades: Dict[str, Any]) -> None:
        """
        Prompt user for trade execution decisions.

        Args:
            validated_trades: Dictionary of validated trade opportunities
        """
        approved_trades = []

        for symbol, trade_info in validated_trades.items():
            if not trade_info.get("recommended_for_human", False):
                continue

            risk_validation = trade_info["risk_validation"]
            trade_summary = risk_validation["trade_summary"]

            print(f"\n{'='*40}")
            print(f"EXECUTE TRADE: {symbol}?")
            print(f"{'='*40}")
            print(f"Entry Price: ${trade_summary['entry_price']:.2f}")
            print(f"Shares: {trade_summary['recommended_shares']}")
            print(f"Position Value: ${trade_summary['position_value']:,.2f}")
            print(f"Risk Amount: ${trade_summary['risk_amount']:,.2f}")
            print(f"Stop Loss: ${trade_summary['stop_loss_price']:.2f}")

            while True:
                response = input("\nExecute this trade? [y/n/q]: ").lower().strip()
                if response == "y":
                    approved_trades.append((symbol, risk_validation))
                    print("✅ Trade approved for execution")
                    break
                elif response == "n":
                    print("❌ Trade declined")
                    break
                elif response == "q":
                    print("⏹️  Execution cancelled")
                    return
                else:
                    print("Please enter 'y' for yes, 'n' for no, or 'q' to quit")

        # Execute approved trades
        if approved_trades:
            print(f"\n🔄 EXECUTING {len(approved_trades)} APPROVED TRADES")
            print("=" * 50)

            for symbol, validation_result in approved_trades:
                print(f"\nExecuting {symbol}...")
                execution_result = self.orchestrator.execute_approved_trade(
                    symbol, validation_result
                )

                if execution_result.get("execution_result", {}).get("status") == "FILLED":
                    print(f"✅ {symbol} trade executed successfully")
                else:
                    error = execution_result.get("error") or execution_result.get(
                        "execution_result", {}
                    ).get("reason", "Unknown error")
                    print(f"❌ {symbol} execution failed: {error}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="RH2MAS Trading System CLI")
    parser.add_argument(
        "--capital", type=float, default=100000, help="Initial capital (default: $100,000)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan command
    scan_parser = subparsers.add_parser("scan", help="Scan market for opportunities")
    scan_parser.add_argument("--symbols", nargs="+", help="Symbols to scan")
    scan_parser.add_argument("--execute", action="store_true", help="Prompt for trade execution")

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor existing positions")

    # Status command
    status_parser = subparsers.add_parser("status", help="Show system status")

    # Close command
    close_parser = subparsers.add_parser("close", help="Close position")
    close_parser.add_argument("symbol", help="Symbol to close")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize CLI
    cli = TradingCLI(initial_capital=args.capital)

    try:
        if args.command == "scan":
            cli.scan_market(args.symbols, args.execute)
        elif args.command == "monitor":
            cli.monitor_positions()
        elif args.command == "status":
            cli.show_status()
        elif args.command == "close":
            cli.close_position(args.symbol)
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        cli.orchestrator.shutdown()


if __name__ == "__main__":
    main()
