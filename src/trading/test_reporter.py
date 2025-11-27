"""
Test Reporter - Generate daily, weekly, and final test reports.

Issue #324: Forward Testing Protocol
Creates formatted reports for forward testing progress and final validation.

Report Types:
- Daily summaries
- Weekly progress reports
- Final validation report with go/no-go recommendation
"""

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.trading.forward_test_manager import ForwardTestManager
from src.trading.performance_validator import PerformanceValidator

logger = logging.getLogger(__name__)


class TestReporter:
    """
    Generate forward testing reports.

    Creates human-readable reports for tracking test progress
    and making go-live decisions.
    """

    def __init__(self, output_dir: Path = Path("reports/forward_tests")):
        """
        Initialize reporter.

        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_daily_summary(
        self, test_manager: ForwardTestManager, validator: PerformanceValidator
    ) -> str:
        """
        Generate daily performance summary.

        Args:
            test_manager: Test manager with current state
            validator: Performance validator

        Returns:
            Formatted daily report
        """
        stats = test_manager.get_test_stats()
        metrics = validator.calculate_metrics(
            test_manager.trades, test_manager.start_date or date.today()
        )

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"DAILY FORWARD TEST SUMMARY - {date.today().strftime('%Y-%m-%d')}")
        report_lines.append("=" * 80)

        report_lines.append(f"\nTest: {stats['test_name']}")
        report_lines.append(f"Day {stats['days_running']} of 30")
        report_lines.append(f"Started: {stats['start_date']}")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("TODAY'S ACTIVITY")
        report_lines.append("-" * 80)

        # Today's signals
        today_signals = [s for s in test_manager.signals if s.timestamp.date() == date.today()]
        report_lines.append(f"Signals Generated: {len(today_signals)}")

        if today_signals:
            for signal in today_signals:
                report_lines.append(
                    f"  • {signal.signal_type.value.upper()} {signal.symbol} "
                    f"@ ${signal.price:.2f} (confidence: {signal.confidence:.1%})"
                )

        # Today's P&L
        today_str = date.today().isoformat()
        today_pnl = test_manager.daily_pnl.get(today_str, 0.0)
        report_lines.append(f"\nToday's P&L: ${today_pnl:+,.2f}")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("CUMULATIVE PERFORMANCE")
        report_lines.append("-" * 80)

        report_lines.append(f"Total Trades: {metrics.total_trades}")
        report_lines.append(
            f"Win Rate: {metrics.win_rate:.1%} "
            f"({metrics.winning_trades}W / {metrics.losing_trades}L)"
        )
        report_lines.append(
            f"Total Return: ${metrics.total_return:+,.2f} ({metrics.total_return_pct:+.2f}%)"
        )
        report_lines.append(f"Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
        report_lines.append(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
        report_lines.append(f"Profit Factor: {metrics.profit_factor:.2f}")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("ACCEPTANCE CRITERIA PROGRESS")
        report_lines.append("-" * 80)

        criteria = {
            "20+ Trades": (metrics.total_trades, ">=", 20),
            "50%+ Win Rate": (metrics.win_rate * 100, ">=", 50),
            "Positive Return": (metrics.total_return, ">", 0),
            "<15% Drawdown": (abs(metrics.max_drawdown_pct), "<", 15),
            ">0.5 Sharpe": (metrics.sharpe_ratio, ">", 0.5),
        }

        for name, (value, op, target) in criteria.items():
            if op == ">=":
                passed = value >= target
            elif op == ">":
                passed = value > target
            else:  # "<"
                passed = value < target

            status = "✓" if passed else "✗"
            report_lines.append(f"{status} {name}: {value:.2f} {op} {target}")

        report_lines.append("\n" + "=" * 80)

        report = "\n".join(report_lines)

        # Save to file
        filename = f"daily_summary_{date.today().isoformat()}.txt"
        filepath = self.output_dir / filename
        filepath.write_text(report)

        logger.info(f"Generated daily summary: {filepath}")
        return report

    def generate_weekly_report(
        self, test_manager: ForwardTestManager, validator: PerformanceValidator, week_number: int
    ) -> str:
        """
        Generate weekly progress report.

        Args:
            test_manager: Test manager
            validator: Performance validator
            week_number: Week number (1-4)

        Returns:
            Formatted weekly report
        """
        metrics = validator.calculate_metrics(
            test_manager.trades, test_manager.start_date or date.today()
        )

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"WEEK {week_number} PROGRESS REPORT")
        report_lines.append("=" * 80)

        report_lines.append(f"\nTest: {test_manager.test_name}")
        report_lines.append(f"Completed: {week_number * 7} days of 30")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("WEEKLY HIGHLIGHTS")
        report_lines.append("-" * 80)

        # Best and worst trades of the week
        closed_trades = [
            t for t in test_manager.trades if t.pnl is not None and t.exit_time is not None
        ]

        if closed_trades:
            best_trade = max(closed_trades, key=lambda t: t.pnl or 0)
            worst_trade = min(closed_trades, key=lambda t: t.pnl or 0)

            report_lines.append(f"Best Trade: {best_trade.symbol} ${best_trade.pnl:+,.2f}")
            report_lines.append(f"Worst Trade: {worst_trade.symbol} ${worst_trade.pnl:+,.2f}")

        report_lines.append(f"\nAverage Trade Duration: {metrics.avg_trade_duration_days:.1f} days")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("PERFORMANCE METRICS")
        report_lines.append("-" * 80)

        report_lines.append(f"Total Trades: {metrics.total_trades}")
        report_lines.append(f"Win Rate: {metrics.win_rate:.1%}")
        report_lines.append(
            f"Total Return: ${metrics.total_return:+,.2f} ({metrics.total_return_pct:+.2f}%)"
        )
        report_lines.append(f"Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
        report_lines.append(f"Max Drawdown: {metrics.max_drawdown_pct:.2f}%")

        report_lines.append("\n" + "=" * 80)

        report = "\n".join(report_lines)

        # Save to file
        filename = f"week_{week_number}_report.txt"
        filepath = self.output_dir / filename
        filepath.write_text(report)

        logger.info(f"Generated week {week_number} report: {filepath}")
        return report

    def generate_final_report(
        self,
        test_manager: ForwardTestManager,
        validator: PerformanceValidator,
        benchmark_return: Optional[float] = None,
    ) -> str:
        """
        Generate final validation report with go/no-go recommendation.

        Args:
            test_manager: Test manager
            validator: Performance validator
            benchmark_return: Benchmark return for comparison (e.g., SPY)

        Returns:
            Formatted final report
        """
        metrics = validator.calculate_metrics(
            test_manager.trades, test_manager.start_date or date.today()
        )

        if benchmark_return is not None:
            metrics = validator.compare_to_benchmark(metrics, benchmark_return)

        passes_criteria = metrics.passes_criteria()

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("FINAL VALIDATION REPORT - 30-DAY FORWARD TEST")
        report_lines.append("=" * 80)

        report_lines.append(f"\nTest: {test_manager.test_name}")
        report_lines.append(f"Period: {test_manager.start_date} to {date.today()}")
        report_lines.append(f"Duration: {metrics.total_days} days")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("FINAL PERFORMANCE METRICS")
        report_lines.append("-" * 80)

        report_lines.append("\nTrade Statistics:")
        report_lines.append(f"  Total Trades: {metrics.total_trades}")
        report_lines.append(f"  Winning Trades: {metrics.winning_trades}")
        report_lines.append(f"  Losing Trades: {metrics.losing_trades}")
        report_lines.append(f"  Win Rate: {metrics.win_rate:.2%}")

        report_lines.append("\nReturn Metrics:")
        report_lines.append(f"  Initial Capital: ${test_manager.initial_capital:,.2f}")
        report_lines.append(f"  Total Return: ${metrics.total_return:+,.2f}")
        report_lines.append(f"  Return %: {metrics.total_return_pct:+.2f}%")
        report_lines.append(f"  Average Win: ${metrics.avg_win:.2f}")
        report_lines.append(f"  Average Loss: ${metrics.avg_loss:.2f}")
        report_lines.append(f"  Profit Factor: {metrics.profit_factor:.2f}")

        report_lines.append("\nRisk Metrics:")
        report_lines.append(f"  Sharpe Ratio: {metrics.sharpe_ratio:.3f}")
        report_lines.append(
            f"  Max Drawdown: ${metrics.max_drawdown:.2f} ({metrics.max_drawdown_pct:.2f}%)"
        )
        report_lines.append(f"  Avg Trade Duration: {metrics.avg_trade_duration_days:.1f} days")

        if metrics.benchmark_return is not None:
            report_lines.append("\nBenchmark Comparison:")
            report_lines.append(f"  Strategy Return: ${metrics.total_return:+,.2f}")
            report_lines.append(f"  Benchmark Return: ${metrics.benchmark_return:+,.2f}")
            report_lines.append(f"  Excess Return: ${metrics.excess_return:+,.2f}")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("ACCEPTANCE CRITERIA VALIDATION")
        report_lines.append("-" * 80)

        criteria_results = [
            ("20+ Trades Generated", metrics.total_trades >= 20, metrics.total_trades),
            ("Win Rate ≥50%", metrics.win_rate >= 0.50, f"{metrics.win_rate:.1%}"),
            ("Positive Return", metrics.total_return > 0, f"${metrics.total_return:+,.2f}"),
            (
                "Max Drawdown <15%",
                abs(metrics.max_drawdown_pct) < 15.0,
                f"{metrics.max_drawdown_pct:.2f}%",
            ),
            ("Sharpe Ratio >0.5", metrics.sharpe_ratio > 0.5, f"{metrics.sharpe_ratio:.3f}"),
        ]

        for criterion, passed, value in criteria_results:
            status = "✓ PASS" if passed else "✗ FAIL"
            report_lines.append(f"{status} - {criterion}: {value}")

        report_lines.append("\n" + "-" * 80)
        report_lines.append("GO-LIVE RECOMMENDATION")
        report_lines.append("-" * 80)

        if passes_criteria:
            report_lines.append("\n✅ **APPROVED FOR LIVE TRADING**")
            report_lines.append("\nAll acceptance criteria have been met.")
            report_lines.append(
                "System has demonstrated reliable performance over 30-day test period."
            )
            report_lines.append("\nRecommendation: Proceed to live trading deployment.")
        else:
            report_lines.append("\n❌ **NOT APPROVED FOR LIVE TRADING**")
            report_lines.append("\nOne or more acceptance criteria not met.")
            report_lines.append(
                "\nRecommendation: Additional optimization and testing "
                "required before live deployment."
            )

        report_lines.append("\n" + "=" * 80)
        report_lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)

        report = "\n".join(report_lines)

        # Save to file
        filename = f"final_validation_report_{date.today().isoformat()}.txt"
        filepath = self.output_dir / filename
        filepath.write_text(report)

        logger.info(f"Generated final validation report: {filepath}")
        logger.info(f"Go-live approval: {'APPROVED' if passes_criteria else 'NOT APPROVED'}")

        return report
