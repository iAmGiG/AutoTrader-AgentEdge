"""
Path-Dependent Backtesting Engine (#525)

Moves beyond vectorized (Close-to-Close) backtesting to simulate intraday
path dependence. This is critical for validating strategies that use
Stop Losses, Take Profits, or Trailing Stops in production.

Key Features:
- Simulates OHLC path (Open -> Low/High -> Close)
- Checks Stop Loss and Take Profit hits intraday
- Conservative assumption: In a single candle, if both SL and TP could be hit,
  we assume the Stop Loss was hit first (worst-case execution).

Usage:
    from scripts.research.path_dependent_simulation import run_path_dependent_backtest
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class Trade:
    """Record of a single trade."""

    symbol: str
    direction: int  # 1 for Long, -1 for Short
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    exit_reason: str  # 'signal_flip', 'stop_loss', 'take_profit', 'trailing_stop', 'eod'
    pnl_pct: float
    holding_days: int


def run_path_dependent_backtest(  # noqa: C901
    ohlc_data: pd.DataFrame,
    signals: pd.Series,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    trailing_stop_pct: Optional[float] = None,
) -> Tuple[pd.DataFrame, List[Trade]]:
    """
    Run a path-dependent backtest using OHLC data.

    Args:
        ohlc_data: DataFrame with 'open', 'high', 'low', 'close' columns.
        signals: Series of target positions (1, 0, -1).
        stop_loss_pct: Fixed stop loss percentage (e.g., 0.05 for 5%).
        take_profit_pct: Fixed take profit percentage.
        trailing_stop_pct: Trailing stop percentage.

    Returns:
        Tuple of (equity_curve, trade_list)
    """
    # Align signals to data
    common_index = ohlc_data.index.intersection(signals.index)
    df = ohlc_data.loc[common_index].copy()
    sig = signals.loc[common_index]

    # State variables
    position = 0  # 0, 1, -1
    entry_price = 0.0
    entry_date = None
    highest_price = 0.0  # For trailing stop (Long)
    lowest_price = np.inf  # For trailing stop (Short)

    cash = 10000.0
    equity_curve = []
    trades: List[Trade] = []

    # Iterate day by day (Vectorization is hard for path-dependent logic)
    for date, row in df.iterrows():
        target_signal = sig.loc[date]

        # 1. Check Exits for Existing Position (Intraday)
        if position != 0:
            exit_price = None
            reason = ""

            # OHLC values for the day
            # Conservative assumption: Open -> Low -> High -> Close (for Longs)
            # This assumes we get stopped out at Low before hitting High target
            day_open = row["open"]
            day_low = row["low"]
            day_high = row["high"]
            day_close = row["close"]

            # --- LONG POSITION LOGIC ---
            if position == 1:
                # Update Trailing High
                highest_price = max(highest_price, day_high)

                # Calculate Stop Levels
                sl_price = entry_price * (1 - stop_loss_pct) if stop_loss_pct else -np.inf
                tp_price = entry_price * (1 + take_profit_pct) if take_profit_pct else np.inf
                ts_price = highest_price * (1 - trailing_stop_pct) if trailing_stop_pct else -np.inf

                effective_stop = max(sl_price, ts_price)

                # Check Stop Loss / Trailing Stop (Priority 1: Safety)
                if day_low <= effective_stop:
                    # We assume slippage on stop: execute at stop price or Open if gap down
                    exit_price = min(day_open, effective_stop)
                    reason = "stop_loss" if effective_stop == sl_price else "trailing_stop"

                # Check Take Profit (Priority 2: Greed)
                elif day_high >= tp_price:
                    exit_price = tp_price
                    reason = "take_profit"

                # Check Signal Flip (Priority 3: Strategy Change)
                elif target_signal != 1:
                    exit_price = day_close
                    reason = "signal_flip"

            # --- SHORT POSITION LOGIC ---
            elif position == -1:
                lowest_price = min(lowest_price, day_low)

                sl_price = entry_price * (1 + stop_loss_pct) if stop_loss_pct else np.inf
                tp_price = entry_price * (1 - take_profit_pct) if take_profit_pct else -np.inf
                ts_price = lowest_price * (1 + trailing_stop_pct) if trailing_stop_pct else np.inf

                effective_stop = min(sl_price, ts_price)

                if day_high >= effective_stop:
                    exit_price = max(day_open, effective_stop)
                    reason = "stop_loss" if effective_stop == sl_price else "trailing_stop"
                elif day_low <= tp_price:
                    exit_price = tp_price
                    reason = "take_profit"
                elif target_signal != -1:
                    exit_price = day_close
                    reason = "signal_flip"

            # Execute Exit
            if exit_price is not None:
                pnl = (exit_price - entry_price) / entry_price * position
                cash *= 1 + pnl
                holding_days = (date - entry_date).days if entry_date else 0
                trades.append(
                    Trade(
                        symbol="N/A",
                        direction=position,
                        entry_date=entry_date,
                        entry_price=entry_price,
                        exit_date=date,
                        exit_price=exit_price,
                        exit_reason=reason,
                        pnl_pct=pnl,
                        holding_days=holding_days,
                    )
                )
                position = 0
                entry_price = 0.0
                entry_date = None

        # 2. Check Entries (if flat)
        # We assume entry at Close to match signal generation logic (t+1 usually)
        # Or entry at Open of NEXT day. Here we simplify to Close for signal alignment.
        if position == 0 and target_signal != 0:
            position = int(target_signal)
            entry_price = row["close"]
            entry_date = date
            highest_price = entry_price
            lowest_price = entry_price

        # Record Equity
        current_val = cash
        if position == 1:
            current_val = cash * (row["close"] / entry_price)
        elif position == -1:
            # Short equity approx
            current_val = cash * (1 + (entry_price - row["close"]) / entry_price)

        equity_curve.append(current_val)

    return pd.DataFrame({"equity": equity_curve}, index=df.index), trades


def calculate_trade_statistics(trades: List[Trade]) -> dict:
    """Calculate summary statistics from a list of trades."""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "avg_pnl_pct": 0.0,
            "exit_reasons": {},
        }

    pnls = [t.pnl_pct for t in trades]
    wins = sum(1 for p in pnls if p > 0)

    exit_reasons = {}
    for t in trades:
        exit_reasons[t.exit_reason] = exit_reasons.get(t.exit_reason, 0) + 1

    return {
        "total_trades": len(trades),
        "win_rate": float(wins / len(trades)) if trades else 0.0,
        "avg_pnl_pct": float(np.mean(pnls)),
        "max_pnl_pct": float(max(pnls)),
        "min_pnl_pct": float(min(pnls)),
        "avg_holding_days": float(np.mean([t.holding_days for t in trades])),
        "exit_reasons": exit_reasons,
    }


if __name__ == "__main__":
    # Example usage with synthetic data
    print("Path-Dependent Simulation Engine (#525)")
    print("=" * 50)
    print()
    print("This module provides path-dependent backtesting that accounts for")
    print("intraday stop-loss and take-profit triggers.")
    print()
    print("Key difference from vectorized backtesting:")
    print("  - Vectorized: signal * daily_return (assumes hold till close)")
    print("  - Path-dependent: checks if SL/TP hit intraday before close")
    print()
    print("Usage:")
    print("  from scripts.research.path_dependent_simulation import (")
    print("      run_path_dependent_backtest,")
    print("      calculate_trade_statistics")
    print("  )")
