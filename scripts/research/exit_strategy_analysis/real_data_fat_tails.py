"""
Real Market Fat Tails Validation (#542).

Tests exit strategies (TP/SL) on real historical periods including crashes
to validate whether conclusions from synthetic data hold under fat-tailed
distributions.

Periods: COVID crash, COVID recovery, 2022 bear, 2023 bull, normal.
Configs: Conservative (6%TP/8%SL), Balanced (8%TP/5%SL), Aggressive (10%TP/3%SL).

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/exit_strategy_analysis/real_data_fat_tails.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import importlib.util

from src.backtesting.research_backtester import ResearchBacktester

# Import indicators via spec loader to avoid src.trading.__init__ Alpaca conflict
_ind_path = (
    Path(__file__).parent.parent.parent.parent / "src" / "trading" / "instruments" / "indicators.py"
)
_spec = importlib.util.spec_from_file_location("indicators", _ind_path)
_ind = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ind)
calculate_macd = _ind.calculate_macd
calculate_rsi = _ind.calculate_rsi

RESULTS_DIR = Path("docs/08_research/03_gex_research")

PERIODS = {
    "covid_crash": ("2020-02-19", "2020-03-23"),
    "covid_recovery": ("2020-03-24", "2020-08-31"),
    "bear_2022": ("2022-01-03", "2022-10-12"),
    "bull_2023": ("2023-01-03", "2023-12-29"),
    "full": ("2020-01-02", "2023-12-29"),
}

CONFIGS = {
    "conservative": {"take_profit": 0.06, "stop_loss": 0.08},
    "balanced": {"take_profit": 0.08, "stop_loss": 0.05},
    "aggressive": {"take_profit": 0.10, "stop_loss": 0.03},
}


def _to_native(obj):
    """Recursively convert numpy types to Python natives for YAML serialization."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def run_exit_backtest(prices: pd.Series, take_profit: float, stop_loss: float) -> dict:
    """Run MACD+RSI backtest with TP/SL exit strategy on a price series.

    Returns trade-level statistics.
    """
    if len(prices) < 40:
        return {"error": "insufficient_data", "n_days": len(prices)}

    # Calculate indicators
    macd_data = calculate_macd(prices)
    rsi_data = calculate_rsi(prices)
    macd_bull = macd_data["bullish"]
    rsi_bull = rsi_data["bullish"]
    entry_signals = (macd_bull & rsi_bull).shift(1).fillna(False)

    trades = []
    position = None

    for i in range(1, len(prices)):
        price = prices.iloc[i]

        if position is None and entry_signals.iloc[i]:
            position = {"entry_price": price, "entry_idx": i}

        elif position is not None:
            entry = position["entry_price"]
            pnl_pct = (price - entry) / entry

            exit_reason = None
            if pnl_pct >= take_profit:
                exit_reason = "take_profit"
            elif pnl_pct <= -stop_loss:
                exit_reason = "stop_loss"
            elif i == len(prices) - 1:
                exit_reason = "end_of_period"

            if exit_reason:
                trades.append(
                    {
                        "pnl_pct": float(pnl_pct),
                        "holding_days": i - position["entry_idx"],
                        "exit_reason": exit_reason,
                    }
                )
                position = None

    if not trades:
        return {"n_trades": 0, "n_days": len(prices)}

    pnls = [t["pnl_pct"] for t in trades]
    stop_outs = [t for t in trades if t["exit_reason"] == "stop_loss"]
    tp_hits = [t for t in trades if t["exit_reason"] == "take_profit"]

    return {
        "n_trades": len(trades),
        "n_days": len(prices),
        "mean_pnl_pct": round(float(np.mean(pnls)) * 100, 3),
        "median_pnl_pct": round(float(np.median(pnls)) * 100, 3),
        "win_rate_pct": round(float(np.mean([p > 0 for p in pnls])) * 100, 1),
        "stop_out_rate_pct": round(len(stop_outs) / len(trades) * 100, 1),
        "tp_hit_rate_pct": round(len(tp_hits) / len(trades) * 100, 1),
        "max_adverse_pct": round(float(min(pnls)) * 100, 2),
        "avg_holding_days": round(float(np.mean([t["holding_days"] for t in trades])), 1),
    }


def analyze_distribution(returns: pd.Series) -> dict:
    """Calculate distribution statistics for a return series."""
    clean = returns.dropna()
    if len(clean) < 5:
        return {"n_obs": len(clean)}

    return {
        "n_obs": len(clean),
        "mean_pct": round(float(clean.mean()) * 100, 4),
        "std_pct": round(float(clean.std()) * 100, 4),
        "skewness": round(float(sp_stats.skew(clean)), 4),
        "kurtosis": round(float(sp_stats.kurtosis(clean)), 4),
        "min_pct": round(float(clean.min()) * 100, 2),
        "max_pct": round(float(clean.max()) * 100, 2),
        "jarque_bera_p": (
            round(float(sp_stats.jarque_bera(clean).pvalue), 4) if len(clean) >= 8 else None
        ),
    }


def main():
    print("=" * 60)
    print("  REAL MARKET FAT TAILS VALIDATION (#542)")
    print("=" * 60)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")

    bt = ResearchBacktester(initial_capital=100_000)

    # Fetch full SPY data
    all_prices_df = bt.fetch_equity_prices(["SPY"], "2020-01-02", "2023-12-29")
    spy_prices = all_prices_df[all_prices_df["symbol"] == "SPY"].set_index("trading_date")["close"]
    spy_prices = spy_prices.sort_index()
    spy_returns = spy_prices.pct_change().dropna()

    print(f"  SPY data: {len(spy_prices)} days")

    results = {}

    for period_name, (start, end) in PERIODS.items():
        print(f"\n  --- {period_name} ({start} → {end}) ---")

        mask = (spy_prices.index >= pd.Timestamp(start)) & (spy_prices.index <= pd.Timestamp(end))
        period_prices = spy_prices[mask]
        _period_returns = spy_returns[  # noqa: F841
            mask[:-1] if len(mask) > len(spy_returns) else mask[: len(spy_returns)]
        ]

        if len(period_prices) < 10:
            print(f"    Insufficient data ({len(period_prices)} days)")
            continue

        # Distribution stats
        period_ret_mask = (spy_returns.index >= pd.Timestamp(start)) & (
            spy_returns.index <= pd.Timestamp(end)
        )
        dist = analyze_distribution(spy_returns[period_ret_mask])
        print(
            f"    Distribution: skew={dist.get('skewness', 'N/A')}, "
            f"kurtosis={dist.get('kurtosis', 'N/A')}"
        )

        # Exit strategy performance
        config_results = {}
        for config_name, params in CONFIGS.items():
            r = run_exit_backtest(period_prices, **params)
            config_results[config_name] = r
            if "n_trades" in r and r["n_trades"] > 0:
                print(
                    f"    {config_name}: {r['n_trades']} trades, "
                    f"win={r.get('win_rate_pct', 0):.1f}%, "
                    f"stop_out={r.get('stop_out_rate_pct', 0):.1f}%, "
                    f"mean_pnl={r.get('mean_pnl_pct', 0):.3f}%"
                )

        results[period_name] = {
            "period": f"{start} to {end}",
            "distribution": dist,
            "exit_strategies": config_results,
        }

    bt.close()

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY: Optimal Strategy by Period")
    print(f"{'='*60}")
    for period_name, data in results.items():
        strategies = data.get("exit_strategies", {})
        best = None
        best_pnl = -999
        for name, r in strategies.items():
            pnl = r.get("mean_pnl_pct", -999)
            if pnl > best_pnl:
                best_pnl = pnl
                best = name
        if best:
            print(f"  {period_name}: {best} (mean PnL={best_pnl:.3f}%)")

    # Save YAML
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#542",
        "description": "Real Market Fat Tails Validation",
        "methodology": {
            "symbol": "SPY",
            "periods": {k: f"{v[0]} to {v[1]}" for k, v in PERIODS.items()},
            "exit_configs": CONFIGS,
            "signal": "MACD(13/34/8) + RSI(14/30/70) consensus",
            "look_ahead_prevention": "shift(1)",
            "distribution_tests": ["skewness", "kurtosis", "Jarque-Bera"],
        },
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / "fat_tails_results.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")


if __name__ == "__main__":
    main()
