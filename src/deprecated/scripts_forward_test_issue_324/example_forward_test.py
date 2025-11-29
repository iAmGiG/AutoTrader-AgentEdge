"""
Example Forward Test - Demonstrates how to use the forward testing framework.

This example shows how to:
1. Initialize a forward test
2. Record signals and trades
3. Generate performance reports

This is a demonstration only - in production, signals and trades
would come from your actual trading system (VoterAgent, etc.).
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.trading.forward_test_manager import (ForwardTestManager, SignalType,
                                              TradeOutcome)
from src.trading.performance_validator import PerformanceValidator
from src.trading.test_reporter import TestReporter


def main():
    """Run example forward test with simulated data."""
    print("=" * 80)
    print("FORWARD TESTING FRAMEWORK - EXAMPLE DEMONSTRATION")
    print("=" * 80)

    # Initialize components
    print("\n1. Initializing test components...")
    test_manager = ForwardTestManager("example_test_2025")
    validator = PerformanceValidator(initial_capital=10000.0)
    reporter = TestReporter()

    # Start test
    print("2. Starting forward test...")
    test_manager.start_test(initial_capital=10000.0)

    # Simulate some signals and trades
    print("3. Simulating signals and trades...")

    symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "META"]
    base_time = datetime.now() - timedelta(days=15)  # 15 days ago

    trade_counter = 0

    for day in range(15):
        current_time = base_time + timedelta(days=day)

        # Generate 1-3 signals per day
        num_signals = random.randint(1, 3)

        for _ in range(num_signals):
            symbol = random.choice(symbols)
            price = random.uniform(150, 200)
            confidence = random.uniform(0.6, 0.9)

            # Record signal
            _signal = test_manager.record_signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                confidence=confidence,
                price=price,
                indicators={"macd": random.uniform(-2, 2), "rsi": random.uniform(30, 70)},
            )

            # 60% chance to execute trade on signal
            if random.random() < 0.6:
                trade_counter += 1
                trade_id = f"TR_{trade_counter:03d}"

                entry_price = price
                quantity = random.randint(5, 20)
                stop_price = entry_price * 0.95  # 5% stop
                target_price = entry_price * 1.08  # 8% target

                # Record trade entry
                _trade = test_manager.record_trade(
                    trade_id=trade_id,
                    symbol=symbol,
                    entry_time=current_time,
                    entry_price=entry_price,
                    quantity=quantity,
                    side="buy",
                    stop_price=stop_price,
                    target_price=target_price,
                )

                # Simulate trade exit (70% win rate for demo)
                exit_days = random.randint(1, 5)
                exit_time = current_time + timedelta(days=exit_days)

                if random.random() < 0.70:  # Win
                    exit_price = random.uniform(entry_price * 1.02, entry_price * 1.10)
                    outcome = TradeOutcome.CLOSED_WIN
                else:  # Loss
                    exit_price = random.uniform(entry_price * 0.95, entry_price * 0.99)
                    outcome = TradeOutcome.CLOSED_LOSS

                test_manager.close_trade(
                    trade_id=trade_id, exit_time=exit_time, exit_price=exit_price, outcome=outcome
                )

    # Get statistics
    print("\n4. Calculating performance metrics...")
    stats = test_manager.get_test_stats()

    print("\nTest Statistics:")
    print(f"  Total Signals: {stats['total_signals']}")
    print(f"  Total Trades: {stats['total_trades']}")
    print(f"  Win Rate: {stats['win_rate']:.1%}")
    print(f"  Total P&L: ${stats['total_pnl']:+,.2f} ({stats['pnl_percent']:+.2f}%)")

    # Generate daily report
    print("\n5. Generating daily report...")
    _daily_report = reporter.generate_daily_summary(test_manager, validator)

    # Generate final report (simulated - normally after 30 days)
    print("\n6. Generating final validation report...")
    _final_report = reporter.generate_final_report(
        test_manager, validator, benchmark_return=250.00  # Simulated SPY return
    )

    print("\n" + "=" * 80)
    print("EXAMPLE COMPLETE")
    print("=" * 80)
    print("\nReports saved to: reports/forward_tests/")
    print("Test state saved to: state/forward_tests/example_test_2025_state.json")
    print("\nTo view full reports, check the files above.")


if __name__ == "__main__":
    main()
