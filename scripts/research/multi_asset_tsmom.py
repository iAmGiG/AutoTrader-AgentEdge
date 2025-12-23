"""
Multi-Asset Time-Series Momentum Research (#498)

Test TSMOM (Time-Series Momentum) across different asset classes:
- Equities (SPY, QQQ, IWM)
- Leveraged (TQQQ, SOXL)
- Bonds (TLT, IEF)
- Volatility (UVXY, VXX)
- Commodities (GLD, SLV)

Walk-forward validation with 2016-2020 train, 2021-2024 test.

Usage:
    python scripts/research/multi_asset_tsmom.py
"""

import datetime
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import yaml


def now_iso() -> str:
    """Get current timestamp as ISO string."""
    return datetime.datetime.now().isoformat()


# Use main repo database path
GEX_DB_PATH = Path("a:/Projects/AutoGen-Trader/.cache/gex_research.db")

# Asset class definitions
ASSET_CLASSES = {
    "equity_index": ["SPY", "QQQ", "IWM"],
    "leveraged_equity": ["TQQQ", "SOXL", "SOXS", "SQQQ"],
    "bonds": ["TLT", "IEF"],
    "volatility": ["UVXY", "VXX"],
    "commodities": ["GLD", "SLV"],
}

# TSMOM lookback periods to test
LOOKBACK_PERIODS = [63, 126, 252]  # ~3mo, ~6mo, ~12mo


@dataclass
class TSMOMResult:
    """Container for TSMOM results."""

    symbol: str
    asset_class: str
    lookback: int
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    in_sample_return: float
    out_of_sample_return: float
    in_sample_trades: int
    out_of_sample_trades: int
    max_drawdown: float
    win_rate: float
    avg_holding_days: float
    regime_performance: Dict[str, float]


def fetch_price_data(symbol: str) -> pd.DataFrame:
    """Fetch daily price data from GEX database."""
    conn = sqlite3.connect(GEX_DB_PATH)
    query = """
        SELECT trading_date, underlying_price
        FROM options_daily_summary
        WHERE symbol = ?
          AND underlying_price IS NOT NULL
        ORDER BY trading_date
    """
    df = pd.read_sql_query(query, conn, params=(symbol,))
    conn.close()

    if df.empty:
        return pd.DataFrame()

    df["trading_date"] = pd.to_datetime(df["trading_date"])
    df = df.set_index("trading_date")
    df = df.rename(columns={"underlying_price": "close"})
    df["returns"] = df["close"].pct_change()

    return df


def calculate_tsmom_signal(
    prices: pd.Series, lookback: int = 252, vol_lookback: int = 21
) -> pd.Series:
    """
    Calculate Time-Series Momentum signal.

    Signal = sign(past_return) * volatility_scaled_position

    Based on Moskowitz, Ooi, Pedersen (2012).
    """
    # Past return
    past_return = prices.pct_change(lookback)

    # Volatility scaling (target annualized vol of 40%)
    daily_vol = prices.pct_change().rolling(vol_lookback).std()
    annualized_vol = daily_vol * np.sqrt(252)

    # Signal: direction * inverse vol scaling
    target_vol = 0.40
    vol_scalar = np.minimum(target_vol / annualized_vol, 2.0)  # Cap at 2x

    signal = np.sign(past_return) * vol_scalar

    return signal


def backtest_tsmom(
    df: pd.DataFrame, lookback: int = 252, initial_capital: float = 10000
) -> Dict[str, Any]:
    """
    Backtest TSMOM strategy.

    Returns comprehensive metrics.
    """
    prices = df["close"]
    signals = calculate_tsmom_signal(prices, lookback)

    position = 0.0
    cash = initial_capital
    holdings = 0.0
    trades = []
    portfolio_values = []
    entry_date = None

    for i in range(lookback + 30, len(df)):
        price = prices.iloc[i]
        signal = signals.iloc[i]
        date = df.index[i]

        if pd.isna(signal):
            signal = 0

        # Portfolio value
        pv = cash + holdings * price
        portfolio_values.append({"date": date, "value": pv})

        # Position sizing based on signal strength
        target_position = signal  # -1 to +1, scaled by vol

        # Rebalance if position change is significant
        if abs(target_position - position) > 0.2:
            # Close existing position
            if holdings != 0:
                cash += holdings * price
                if entry_date:
                    trades.append(
                        {
                            "exit_date": date,
                            "entry_date": entry_date,
                            "pnl": (
                                (price - trades[-1]["entry_price"]) / trades[-1]["entry_price"]
                                if trades and "entry_price" in trades[-1]
                                else 0
                            ),
                        }
                    )
                holdings = 0

            # Open new position
            if target_position != 0:
                position_value = pv * abs(target_position) * 0.95
                if target_position > 0:
                    holdings = position_value / price
                    cash -= position_value
                else:
                    holdings = -position_value / price  # Short
                    cash += position_value

                entry_date = date
                trades.append(
                    {
                        "entry_date": date,
                        "entry_price": price,
                        "direction": np.sign(target_position),
                    }
                )

            position = target_position

    # Final close
    if holdings != 0:
        cash += holdings * prices.iloc[-1]
        portfolio_values[-1]["value"] = cash

    # Calculate metrics
    pv_df = pd.DataFrame(portfolio_values).set_index("date")
    pv_series = pv_df["value"]

    if len(pv_series) < 2:
        return {
            "total_return": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "trades": 0,
            "win_rate": 0,
            "avg_holding_days": 0,
        }

    strategy_returns = pv_series.pct_change().dropna()

    total_return = (pv_series.iloc[-1] - initial_capital) / initial_capital * 100
    sharpe = (
        np.sqrt(252) * strategy_returns.mean() / strategy_returns.std()
        if strategy_returns.std() > 0
        else 0
    )

    # Max drawdown
    rolling_max = pv_series.cummax()
    drawdowns = (pv_series - rolling_max) / rolling_max
    max_drawdown = drawdowns.min() * 100

    # Trade statistics
    completed_trades = [t for t in trades if "pnl" in t]
    win_rate = (
        sum(1 for t in completed_trades if t["pnl"] > 0) / len(completed_trades) * 100
        if completed_trades
        else 0
    )

    # Average holding period
    holding_days = []
    for t in completed_trades:
        if "entry_date" in t and "exit_date" in t:
            days = (t["exit_date"] - t["entry_date"]).days
            holding_days.append(days)
    avg_holding = np.mean(holding_days) if holding_days else 0

    return {
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_drawdown,
        "trades": len([t for t in trades if "entry_price" in t]),
        "win_rate": win_rate,
        "avg_holding_days": avg_holding,
    }


def analyze_regime_performance(
    df: pd.DataFrame, lookback: int, regime_periods: Dict[str, tuple]
) -> Dict[str, float]:
    """Analyze TSMOM performance across different market regimes."""
    regime_sharpes = {}

    for regime_name, (start, end) in regime_periods.items():
        mask = (df.index >= start) & (df.index <= end)
        regime_df = df[mask]

        if len(regime_df) < lookback + 30:
            regime_sharpes[regime_name] = np.nan
            continue

        metrics = backtest_tsmom(regime_df, lookback)
        regime_sharpes[regime_name] = metrics["sharpe_ratio"]

    return regime_sharpes


def run_tsmom_analysis():
    """Run comprehensive TSMOM analysis across asset classes."""
    print("=" * 70)
    print("MULTI-ASSET TSMOM RESEARCH (#498)")
    print("=" * 70)
    print("\nTime-Series Momentum across Asset Classes")
    print("Walk-Forward: Train 2020-2022, Test 2023-2024")
    print("(Adjusted for available data range)")

    # Market regime definitions
    regime_periods = {
        "covid_crash_recovery": ("2020-03-01", "2020-12-31"),
        "bull_2021": ("2021-01-01", "2021-12-31"),
        "bear_2022": ("2022-01-01", "2022-12-31"),
        "recovery_2023_2024": ("2023-01-01", "2024-12-31"),
    }

    results = {
        "run_timestamp": now_iso(),
        "issue": "#498",
        "description": "Multi-Asset TSMOM Analysis",
        "methodology": {
            "in_sample": "2020-01-01 to 2022-12-31",
            "out_of_sample": "2023-01-01 to 2024-12-31",
            "note": "Adjusted for GEX database available data (2020+)",
            "lookback_periods": LOOKBACK_PERIODS,
            "volatility_scaling": True,
            "target_volatility": 0.40,
        },
        "asset_class_results": {},
    }

    all_results = []

    for asset_class, symbols in ASSET_CLASSES.items():
        print(f"\n{'=' * 50}")
        print(f"ASSET CLASS: {asset_class.upper()}")
        print("=" * 50)

        class_results = []

        for symbol in symbols:
            print(f"\n{symbol}:")

            try:
                df = fetch_price_data(symbol)

                if df.empty:
                    print("  No data available")
                    continue

                print(
                    f"  Data range: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} days)"
                )

                # Split into train/test (adjusted for 2020+ data)
                train_df = df[(df.index >= "2020-01-01") & (df.index <= "2022-12-31")]
                test_df = df[(df.index >= "2023-01-01") & (df.index <= "2024-12-31")]

                if len(train_df) < 250:
                    print(f"  Insufficient training data ({len(train_df)} days)")
                    continue

                if len(test_df) < 100:
                    print(f"  Insufficient test data ({len(test_df)} days)")
                    continue

                # Test each lookback period
                for lookback in LOOKBACK_PERIODS:
                    train_metrics = backtest_tsmom(train_df, lookback)
                    test_metrics = backtest_tsmom(test_df, lookback)
                    regime_perf = analyze_regime_performance(df, lookback, regime_periods)

                    result = TSMOMResult(
                        symbol=symbol,
                        asset_class=asset_class,
                        lookback=lookback,
                        in_sample_sharpe=train_metrics["sharpe_ratio"],
                        out_of_sample_sharpe=test_metrics["sharpe_ratio"],
                        in_sample_return=train_metrics["total_return"],
                        out_of_sample_return=test_metrics["total_return"],
                        in_sample_trades=train_metrics["trades"],
                        out_of_sample_trades=test_metrics["trades"],
                        max_drawdown=test_metrics["max_drawdown"],
                        win_rate=test_metrics["win_rate"],
                        avg_holding_days=test_metrics["avg_holding_days"],
                        regime_performance=regime_perf,
                    )

                    class_results.append(result)
                    all_results.append(result)

                    # Report 12-month (252) results
                    if lookback == 252:
                        print(
                            f"  TSMOM-12M: IS Sharpe={train_metrics['sharpe_ratio']:.3f}, "
                            f"OOS Sharpe={test_metrics['sharpe_ratio']:.3f}"
                        )

            except Exception as e:
                print(f"  ERROR: {e}")

        # Aggregate asset class results
        if class_results:
            oos_sharpes = [r.out_of_sample_sharpe for r in class_results if r.lookback == 252]
            avg_oos_sharpe = np.mean(oos_sharpes) if oos_sharpes else 0

            results["asset_class_results"][asset_class] = {
                "symbols_tested": len(set(r.symbol for r in class_results)),
                "avg_oos_sharpe_12m": float(avg_oos_sharpe),
                "best_performer": (
                    max(class_results, key=lambda r: r.out_of_sample_sharpe).symbol
                    if class_results
                    else None
                ),
            }

    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY BY ASSET CLASS")
    print("=" * 70)

    for asset_class, data in results["asset_class_results"].items():
        print(f"\n{asset_class}:")
        print(f"  Symbols tested: {data['symbols_tested']}")
        print(f"  Avg OOS Sharpe (12M): {data['avg_oos_sharpe_12m']:.3f}")
        print(f"  Best performer: {data['best_performer']}")

    # Lookback period comparison
    print("\n" + "=" * 70)
    print("LOOKBACK PERIOD COMPARISON")
    print("=" * 70)

    for lookback in LOOKBACK_PERIODS:
        lookback_results = [r for r in all_results if r.lookback == lookback]
        if lookback_results:
            avg_sharpe = np.mean([r.out_of_sample_sharpe for r in lookback_results])
            print(f"\nLookback {lookback} days (~{lookback//21} months):")
            print(f"  Avg OOS Sharpe: {avg_sharpe:.3f}")
            print(
                f"  Passing (Sharpe > 0.3): {sum(1 for r in lookback_results if r.out_of_sample_sharpe > 0.3)}/{len(lookback_results)}"
            )

    # Regime analysis
    print("\n" + "=" * 70)
    print("REGIME PERFORMANCE (12-Month Lookback)")
    print("=" * 70)

    regime_sharpes = {r: [] for r in regime_periods.keys()}
    for result in all_results:
        if result.lookback == 252:
            for regime, sharpe in result.regime_performance.items():
                if not np.isnan(sharpe):
                    regime_sharpes[regime].append(sharpe)

    for regime, sharpes in regime_sharpes.items():
        if sharpes:
            print(f"\n{regime}:")
            print(f"  Avg Sharpe: {np.mean(sharpes):.3f}")
            print(f"  Positive: {sum(1 for s in sharpes if s > 0)}/{len(sharpes)}")

    # Conclusions
    results["conclusions"] = {
        "best_asset_class": (
            max(
                results["asset_class_results"].items(),
                key=lambda x: x[1]["avg_oos_sharpe_12m"],
            )[0]
            if results["asset_class_results"]
            else None
        ),
        "recommended_lookback": 252,  # Traditional 12-month
        "causal_mechanism": {
            "who": "Trend-following CTAs and momentum funds",
            "whom": "All market participants",
            "what": "Slow information diffusion creates persistent trends",
            "academic_support": "Moskowitz, Ooi, Pedersen (2012)",
        },
    }

    # Convert results for YAML
    def convert_result(r):
        return {
            "symbol": r.symbol,
            "asset_class": r.asset_class,
            "lookback": r.lookback,
            "in_sample_sharpe": float(r.in_sample_sharpe),
            "out_of_sample_sharpe": float(r.out_of_sample_sharpe),
            "in_sample_return": float(r.in_sample_return),
            "out_of_sample_return": float(r.out_of_sample_return),
            "max_drawdown": float(r.max_drawdown),
            "win_rate": float(r.win_rate),
            "regime_performance": {
                k: float(v) if not np.isnan(v) else None for k, v in r.regime_performance.items()
            },
        }

    results["detailed_results"] = [convert_result(r) for r in all_results]

    # Save results
    output = Path("docs/08_research/04_strategy_research/tsmom_multi_asset_results.yaml")
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        yaml.dump(results, f, default_flow_style=False, sort_keys=False)
    print(f"\nResults saved to: {output}")

    return results


def main():
    return run_tsmom_analysis()


if __name__ == "__main__":
    main()
