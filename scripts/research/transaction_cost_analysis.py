"""
Transaction Cost Reality Check (#519)

Retests validated strategies with realistic transaction costs to measure their
robustness to trading friction.

METHODOLOGY CORRECTIONS APPLIED:
1. Cost Model: Costs are now proportional to turnover, not a fixed deduction.
2. MACD+RSI Strategy: Uses trend-confirming RSI and symmetric signals, aligning
   with corrected methodology from macd_parameter_stability.py.

Cost Assumptions (bps per trade, applied to turnover):
- SPY/QQQ: 2 bps per trade
- TQQQ/SOXL: 5 bps per trade
- UVXY: 10 bps per trade
"""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# Constants
EPSILON = 1e-9
MIN_DATA_POINTS = 252

# Transaction cost assumptions (basis points per trade)
COST_ASSUMPTIONS = {
    "SPY": 2,
    "QQQ": 2,
    "IWM": 3,
    "DIA": 2,
    "TQQQ": 5,
    "SOXL": 5,
    "UVXY": 10,
    "VXX": 8,
    "default": 5,  # Conservative default
}

DB_PATH = Path(".cache/gex_research.db")
OUTPUT_PATH = Path("docs/08_research/03_strategy_research/transaction_cost_results.yaml")


@dataclass
class CostAnalysisResult:
    """Results for transaction cost analysis."""

    symbol: str
    strategy: str
    period: str

    # Performance
    gross_sharpe: float
    net_sharpe: float
    gross_return_pct: float
    net_return_pct: float

    # Cost metrics
    total_trades: int
    turnover_annual: float  # Trades per year
    cost_bps: int
    total_cost_pct: float
    cost_drag_pct: float  # (gross - net) / gross

    # Break-even analysis
    breakeven_bps: float  # Max cost before Sharpe < 0.3


def safe_sharpe(returns: pd.Series, annualize: int = 252) -> float:
    """Calculate Sharpe with safeguards."""
    if len(returns) < 2:
        return 0.0

    returns = returns.dropna()
    if len(returns) < 2:
        return 0.0

    std = returns.std()
    if std < EPSILON:
        return 0.0

    sharpe = (returns.mean() / std) * np.sqrt(annualize)
    return float(np.clip(sharpe, -10.0, 10.0))


def get_cost_bps(symbol: str) -> int:
    """Get transaction cost assumption for symbol."""
    return COST_ASSUMPTIONS.get(symbol.upper(), COST_ASSUMPTIONS["default"])


def calculate_tsmom_signals(prices: pd.Series, lookback: int = 252) -> pd.Series:
    """TSMOM: 12-month momentum signals."""
    if len(prices) < lookback + 1:
        return pd.Series(0.0, index=prices.index)

    past_return = (prices - prices.shift(lookback)) / (prices.shift(lookback) + EPSILON)
    signals = np.sign(past_return)
    signals.iloc[:lookback] = 0.0
    signals = signals.shift(1).fillna(0)

    return signals


def calculate_macd_rsi_signals(prices: pd.Series) -> pd.Series:
    """
    MACD+RSI trend-confirming signals.
    Uses corrected methodology from macd_parameter_stability.py, not the flawed
    range-bound RSI filter and asymmetric signals used in older scripts.
    """
    if len(prices) < 40:
        return pd.Series(0.0, index=prices.index)

    # MACD (standard 12/26/9)
    ema_fast = prices.ewm(span=12, adjust=False).mean()
    ema_slow = prices.ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line

    # RSI (14)
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / (loss + EPSILON)  # Add epsilon to prevent division by zero
    rsi = 100 - (100 / (1 + rs))

    # Base MACD signals (symmetric: +1.0 long, -1.0 short)
    signals = pd.Series(0.0, index=prices.index)
    signals[histogram > 0] = 1.0
    signals[histogram <= 0] = -1.0

    # RSI trend confirmation: >50 for long, <50 for short
    long_confirmed = (signals > 0) & (rsi > 50)
    short_confirmed = (signals < 0) & (rsi < 50)
    signals = signals.where(long_confirmed | short_confirmed, 0.0)

    # Zero out warmup and shift for t+1 execution
    signals.iloc[:40] = 0.0
    signals = signals.shift(1).fillna(0)

    return signals


def run_backtest_with_costs(
    prices: pd.Series, signals: pd.Series, cost_bps: int
) -> Tuple[pd.Series, pd.Series, int, float]:
    """
    Run backtest with and without transaction costs. Costs are applied
    proportionally to the portfolio turnover on each trade.

    Returns:
        (gross_returns, net_returns, trade_count, total_cost_pct)
    """
    daily_returns = prices.pct_change()

    # Gross strategy returns (no costs)
    gross_returns = signals * daily_returns

    # Identify trades and calculate turnover (e.g., signal change from -1 to +1 is 2.0)
    turnover = signals.diff().abs()
    trade_mask = turnover > EPSILON
    trade_count = int(trade_mask.sum())

    # Cost per 100% portfolio turnover
    cost_per_turnover = cost_bps / 10000

    # Calculate net returns by subtracting turnover-based costs
    transaction_costs = turnover * cost_per_turnover
    net_returns = gross_returns - transaction_costs

    # Total cost as a percentage of initial capital (sum of all daily costs)
    # This is an approximation assuming capital is constant.
    total_cost_pct = transaction_costs.sum() * 100

    return gross_returns, net_returns, trade_count, total_cost_pct


def calculate_breakeven_cost(
    prices: pd.Series, signals: pd.Series, target_sharpe: float = 0.3
) -> float:
    """
    Find maximum cost in bps that still yields target Sharpe.
    Uses binary search.
    """
    daily_returns = prices.pct_change()
    gross_returns = signals * daily_returns

    gross_sharpe = safe_sharpe(gross_returns)

    if gross_sharpe <= target_sharpe:
        return 0.0  # Already below target

    # Binary search for break-even
    low, high = 0, 100  # 0 to 100 bps
    turnover = signals.diff().abs()

    for _ in range(20):  # Max iterations
        mid_bps = (low + high) / 2
        cost_per_turnover = mid_bps / 10000

        # Apply cost model based on turnover
        transaction_costs = turnover * cost_per_turnover
        net_returns = gross_returns - transaction_costs

        net_sharpe = safe_sharpe(net_returns)

        if net_sharpe > target_sharpe:
            low = mid_bps
        else:
            high = mid_bps

        if high - low < 0.1:
            break

    return round(low, 1)


def get_price_data(conn: sqlite3.Connection, symbol: str) -> Optional[pd.DataFrame]:
    """Fetch price data."""
    query = """
        SELECT trading_date, underlying_price
        FROM options_daily_summary
        WHERE symbol = ? AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))

    if len(df) < MIN_DATA_POINTS:
        return None

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df.set_index("trading_date", inplace=True)
    df.columns = ["close"]

    return df


def analyze_symbol(
    prices: pd.DataFrame, symbol: str, strategy_name: str, signals: pd.Series, cost_bps: int
) -> Optional[CostAnalysisResult]:
    """Analyze transaction costs for a strategy."""
    close = prices["close"]

    # Run backtest
    gross_returns, net_returns, trade_count, total_cost_pct = run_backtest_with_costs(
        close, signals, cost_bps
    )

    gross_sharpe = safe_sharpe(gross_returns)
    net_sharpe = safe_sharpe(net_returns)

    # Total returns
    gross_cumulative = (1 + gross_returns).cumprod()
    net_cumulative = (1 + net_returns).cumprod()

    gross_total_return = (gross_cumulative.iloc[-1] - 1) * 100
    net_total_return = (net_cumulative.iloc[-1] - 1) * 100

    # Annualized turnover
    years = len(prices) / 252
    turnover_annual = trade_count / years if years > 0 else 0

    # Cost drag
    if abs(gross_sharpe) > EPSILON:
        cost_drag = ((gross_sharpe - net_sharpe) / abs(gross_sharpe)) * 100
    else:
        cost_drag = 0.0

    # Break-even cost
    breakeven = calculate_breakeven_cost(close, signals)

    return CostAnalysisResult(
        symbol=symbol,
        strategy=strategy_name,
        period=f"{prices.index.min().date()} to {prices.index.max().date()}",
        gross_sharpe=round(gross_sharpe, 3),
        net_sharpe=round(net_sharpe, 3),
        gross_return_pct=round(gross_total_return, 2),
        net_return_pct=round(net_total_return, 2),
        total_trades=trade_count,
        turnover_annual=round(turnover_annual, 1),
        cost_bps=cost_bps,
        total_cost_pct=round(total_cost_pct, 2),
        cost_drag_pct=round(cost_drag, 1),
        breakeven_bps=breakeven,
    )


def main():  # noqa: C901
    """Main entry point."""
    print("=" * 70)
    print("TRANSACTION COST REALITY CHECK (#519)")
    print("=" * 70)
    print("\nCost assumptions (bps per trade):")
    for sym, cost in COST_ASSUMPTIONS.items():
        if sym != "default":
            print(f"  {sym}: {cost} bps")
    print(f"  default: {COST_ASSUMPTIONS['default']} bps")

    if not DB_PATH.exists():
        print(f"\nERROR: Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    try:
        # Get symbols
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT symbol, COUNT(*) as days
            FROM options_daily_summary
            WHERE underlying_price IS NOT NULL
            GROUP BY symbol
            HAVING days >= ?
            ORDER BY days DESC
        """,
            (MIN_DATA_POINTS,),
        )

        symbols = [(row[0], row[1]) for row in cursor.fetchall()]
        print(f"\nSymbols with sufficient data: {len(symbols)}")

        all_results: List[CostAnalysisResult] = []

        strategies = {
            "TSMOM": calculate_tsmom_signals,
            "MACD+RSI": calculate_macd_rsi_signals,
        }

        for symbol, days in symbols:
            print(f"\n{symbol} ({days} days):")

            prices = get_price_data(conn, symbol)
            if prices is None:
                continue

            cost_bps = get_cost_bps(symbol)

            for strategy_name, signal_func in strategies.items():
                signals = signal_func(prices["close"])

                result = analyze_symbol(prices, symbol, strategy_name, signals, cost_bps)

                if result:
                    all_results.append(result)
                    status = "[PASS]" if result.net_sharpe > 0.3 else "[FAIL]"
                    print(
                        f"  {strategy_name:12s}: "
                        f"Gross={result.gross_sharpe:.2f}, Net={result.net_sharpe:.2f}, "
                        f"Drag={result.cost_drag_pct:.0f}%, "
                        f"Breakeven={result.breakeven_bps:.0f}bps {status}"
                    )

        # Summary by strategy
        print("\n" + "=" * 70)
        print("SUMMARY BY STRATEGY")
        print("=" * 70)

        for strategy_name in strategies:
            strat_results = [r for r in all_results if r.strategy == strategy_name]
            if not strat_results:
                continue

            avg_gross = np.mean([r.gross_sharpe for r in strat_results])
            avg_net = np.mean([r.net_sharpe for r in strat_results])
            avg_drag = np.mean([r.cost_drag_pct for r in strat_results])
            avg_turnover = np.mean([r.turnover_annual for r in strat_results])
            pass_rate = np.mean([r.net_sharpe > 0.3 for r in strat_results]) * 100

            print(f"\n{strategy_name}:")
            print(f"  Avg Gross Sharpe: {avg_gross:.3f}")
            print(f"  Avg Net Sharpe:   {avg_net:.3f}")
            print(f"  Avg Cost Drag:    {avg_drag:.1f}%")
            print(f"  Avg Turnover:     {avg_turnover:.0f} trades/year")
            print(f"  Pass Rate:        {pass_rate:.0f}% (Net Sharpe > 0.3)")

        # Save results
        output_data = {
            "experiment": "Transaction Cost Reality Check",
            "issue": "#519",
            "cost_assumptions_bps": COST_ASSUMPTIONS,
            "methodology": {
                "execution": "t+1 (signal at close, execute next day)",
                "cost_application": "Full spread on each signal change",
                "breakeven_target_sharpe": 0.3,
            },
            "summary_by_strategy": {},
            "detailed_results": [],
        }

        for strategy_name in strategies:
            strat_results = [r for r in all_results if r.strategy == strategy_name]
            if strat_results:
                output_data["summary_by_strategy"][strategy_name] = {
                    "avg_gross_sharpe": float(
                        round(np.mean([r.gross_sharpe for r in strat_results]), 3)
                    ),
                    "avg_net_sharpe": float(
                        round(np.mean([r.net_sharpe for r in strat_results]), 3)
                    ),
                    "avg_cost_drag_pct": float(
                        round(np.mean([r.cost_drag_pct for r in strat_results]), 1)
                    ),
                    "avg_turnover_annual": float(
                        round(np.mean([r.turnover_annual for r in strat_results]), 0)
                    ),
                    "pass_rate_pct": float(
                        round(np.mean([r.net_sharpe > 0.3 for r in strat_results]) * 100, 0)
                    ),
                }

        for r in all_results:
            output_data["detailed_results"].append(
                {
                    "symbol": r.symbol,
                    "strategy": r.strategy,
                    "period": r.period,
                    "gross_sharpe": float(r.gross_sharpe),
                    "net_sharpe": float(r.net_sharpe),
                    "gross_return_pct": float(r.gross_return_pct),
                    "net_return_pct": float(r.net_return_pct),
                    "total_trades": int(r.total_trades),
                    "turnover_annual": float(r.turnover_annual),
                    "cost_bps": int(r.cost_bps),
                    "total_cost_pct": float(r.total_cost_pct),
                    "cost_drag_pct": float(r.cost_drag_pct),
                    "breakeven_bps": float(r.breakeven_bps),
                }
            )

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            yaml.dump(output_data, f, default_flow_style=False, sort_keys=False)

        print(f"\n[OK] Results saved: {OUTPUT_PATH}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
