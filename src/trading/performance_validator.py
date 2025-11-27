"""
Performance Validator - Calculate and validate trading performance metrics.

Issue #324: Forward Testing Protocol
Computes statistical performance metrics and validates against acceptance criteria.

Metrics Calculated:
- Sharpe Ratio
- Win Rate
- Max Drawdown
- Cumulative Return
- Risk-adjusted metrics
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np

from src.trading.forward_test_manager import TradeOutcome, TradeRecord

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    # Basic metrics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float

    # Returns
    total_return: float
    total_return_pct: float
    avg_win: float
    avg_loss: float
    profit_factor: float  # Total wins / Total losses

    # Risk metrics
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float

    # Operational metrics
    avg_trade_duration_days: float
    total_days: int

    # Comparison to benchmark
    benchmark_return: Optional[float] = None
    excess_return: Optional[float] = None

    def passes_criteria(self) -> bool:
        """
        Check if metrics meet minimum acceptance criteria.

        Criteria from Issue #324:
        - Total trades >= 20
        - Win rate >= 50%
        - Total return > 0
        - Max drawdown < 15%
        - Sharpe ratio > 0.5
        """
        checks = {
            "total_trades": self.total_trades >= 20,
            "win_rate": self.win_rate >= 0.50,
            "total_return": self.total_return > 0,
            "max_drawdown": abs(self.max_drawdown_pct) < 15.0,
            "sharpe_ratio": self.sharpe_ratio > 0.5,
        }

        logger.info("Performance Criteria Check:")
        for criterion, passed in checks.items():
            status = "✓" if passed else "✗"
            logger.info(f"  {status} {criterion}: {getattr(self, criterion)}")

        return all(checks.values())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "avg_trade_duration_days": self.avg_trade_duration_days,
            "total_days": self.total_days,
            "benchmark_return": self.benchmark_return,
            "excess_return": self.excess_return,
        }


class PerformanceValidator:
    """
    Calculate and validate trading performance.

    Uses closed trades to compute comprehensive performance metrics
    and validate against acceptance criteria.
    """

    def __init__(self, initial_capital: float = 10000.0, risk_free_rate: float = 0.02):
        """
        Initialize validator.

        Args:
            initial_capital: Starting capital
            risk_free_rate: Annual risk-free rate for Sharpe calculation (default 2%)
        """
        self.initial_capital = initial_capital
        self.risk_free_rate = risk_free_rate

    def calculate_metrics(
        self, trades: List[TradeRecord], start_date: date, end_date: Optional[date] = None
    ) -> PerformanceMetrics:
        """
        Calculate comprehensive performance metrics.

        Args:
            trades: List of trade records
            start_date: Test start date
            end_date: Test end date (default: today)

        Returns:
            PerformanceMetrics with all calculated statistics
        """
        end_date = end_date or date.today()
        total_days = (end_date - start_date).days

        # Filter to closed trades only
        closed_trades = [
            t for t in trades if t.outcome in (TradeOutcome.CLOSED_WIN, TradeOutcome.CLOSED_LOSS)
        ]

        if not closed_trades:
            logger.warning("No closed trades to analyze")
            return self._empty_metrics(total_days)

        # Basic counts
        total_trades = len(closed_trades)
        winning_trades_list = [t for t in closed_trades if t.outcome == TradeOutcome.CLOSED_WIN]
        losing_trades_list = [t for t in closed_trades if t.outcome == TradeOutcome.CLOSED_LOSS]

        winning_trades = len(winning_trades_list)
        losing_trades = len(losing_trades_list)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0.0

        # Return calculations
        total_pnl = sum(t.pnl for t in closed_trades if t.pnl is not None)
        total_return_pct = (total_pnl / self.initial_capital) * 100

        # Average win/loss
        wins = [t.pnl for t in winning_trades_list if t.pnl is not None]
        losses = [abs(t.pnl) for t in losing_trades_list if t.pnl is not None]

        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0

        # Profit factor
        total_wins = sum(wins) if wins else 0.0
        total_losses = sum(losses) if losses else 0.0
        profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

        # Sharpe ratio
        returns = [t.pnl_percent for t in closed_trades if t.pnl_percent is not None]
        sharpe_ratio = self._calculate_sharpe(returns)

        # Drawdown
        max_dd, max_dd_pct = self._calculate_max_drawdown(closed_trades)

        # Trade duration
        durations = []
        for t in closed_trades:
            if t.exit_time and t.entry_time:
                duration = (t.exit_time - t.entry_time).total_seconds() / 86400  # Convert to days
                durations.append(duration)

        avg_duration = np.mean(durations) if durations else 0.0

        return PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_return=total_pnl,
            total_return_pct=total_return_pct,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            avg_trade_duration_days=avg_duration,
            total_days=total_days,
        )

    def _calculate_sharpe(self, returns: List[float]) -> float:
        """
        Calculate Sharpe ratio.

        Args:
            returns: List of percentage returns

        Returns:
            Annualized Sharpe ratio
        """
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns) / 100  # Convert from percent to decimal

        # Calculate mean and std of returns
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array, ddof=1)

        if std_return == 0:
            return 0.0

        # Annualize assuming ~252 trading days per year
        # Sharpe = (mean_return - risk_free_rate) / std_return
        # For simplicity, using per-trade returns without annualization adjustment
        sharpe = (mean_return - (self.risk_free_rate / 252)) / std_return

        # Scale to approximate annual Sharpe
        sharpe_annual = sharpe * np.sqrt(252 / len(returns))

        return sharpe_annual

    def _calculate_max_drawdown(self, trades: List[TradeRecord]) -> tuple[float, float]:
        """
        Calculate maximum drawdown.

        Args:
            trades: Closed trades

        Returns:
            (max_drawdown_dollars, max_drawdown_percent)
        """
        if not trades:
            return 0.0, 0.0

        # Build equity curve
        equity = self.initial_capital
        equity_curve = [equity]

        for trade in sorted(trades, key=lambda t: t.exit_time or t.entry_time):
            if trade.pnl is not None:
                equity += trade.pnl
                equity_curve.append(equity)

        # Calculate drawdown at each point
        peak = equity_curve[0]
        max_dd_dollars = 0.0
        max_dd_pct = 0.0

        for value in equity_curve:
            if value > peak:
                peak = value

            dd_dollars = peak - value
            dd_pct = (dd_dollars / peak) * 100 if peak > 0 else 0.0

            if dd_dollars > max_dd_dollars:
                max_dd_dollars = dd_dollars
                max_dd_pct = dd_pct

        return max_dd_dollars, max_dd_pct

    def _empty_metrics(self, total_days: int) -> PerformanceMetrics:
        """Return empty metrics when no trades available."""
        return PerformanceMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_return=0.0,
            total_return_pct=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            avg_trade_duration_days=0.0,
            total_days=total_days,
        )

    def compare_to_benchmark(
        self, metrics: PerformanceMetrics, benchmark_return: float
    ) -> PerformanceMetrics:
        """
        Add benchmark comparison to metrics.

        Args:
            metrics: Calculated performance metrics
            benchmark_return: Benchmark total return (e.g., SPY buy-and-hold)

        Returns:
            Updated metrics with benchmark comparison
        """
        metrics.benchmark_return = benchmark_return
        metrics.excess_return = metrics.total_return - benchmark_return

        logger.info(
            f"Strategy return: ${metrics.total_return:.2f} ({metrics.total_return_pct:.2f}%)"
        )
        logger.info(f"Benchmark return: ${benchmark_return:.2f}")
        logger.info(f"Excess return: ${metrics.excess_return:.2f}")

        return metrics
