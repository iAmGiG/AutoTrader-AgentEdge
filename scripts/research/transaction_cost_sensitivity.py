"""
Transaction Cost Sensitivity Analysis (#541).

Sweeps commission_bps across the three GEX research strategies (dispersion,
delta neutral, pairs trading) to find breakeven costs, Sharpe degradation
curves, and the cost level where GEX overlay advantage disappears.

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/transaction_cost_sensitivity.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.signals.delta_neutral_signal import DeltaNeutralSignal
from src.backtesting.signals.dispersion_signal import DispersionSignal
from src.backtesting.signals.pairs_trading_signal import PairsTradingSignal


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


COST_LEVELS = [0, 1, 2, 5, 10, 25, 50]  # basis points
FIT_START = "2020-01-02"
FIT_END = "2021-12-31"
TEST_START = "2022-01-03"
TEST_END = "2023-12-29"
RESULTS_DIR = Path("docs/08_research/03_gex_research")


def run_dispersion_sweep() -> list:
    """Sweep commission_bps for dispersion strategy."""
    index = "SPY"
    components = ["XLF", "XLE", "XLK", "XLV", "QQQ", "IWM"]
    all_symbols = [index] + components

    results = []
    for bps in COST_LEVELS:
        bt = ResearchBacktester(initial_capital=100_000, commission_bps=bps)
        try:
            full_prices = bt.get_close_prices(all_symbols, FIT_START, TEST_END)
            full_returns = full_prices.pct_change().dropna()
            available = [c for c in components if c in full_prices.columns]

            signal = DispersionSignal(
                correlation_lookback=60, zscore_lookback=120, entry_z=1.5, exit_z=0.5
            )
            signal.fit(full_returns, index, available)

            test_prices = bt.get_close_prices(all_symbols, TEST_START, TEST_END)
            r = bt.run_daily_signal_strategy(
                signal_fn=signal.generate_signal, prices=test_prices, symbol=index
            )
            results.append(
                {
                    "commission_bps": bps,
                    "sharpe": round(r.sharpe_ratio, 3),
                    "total_return_pct": round(r.total_return, 2),
                    "max_drawdown_pct": round(r.max_drawdown, 2),
                    "num_trades": r.num_trades,
                }
            )
            print(
                f"    Dispersion @ {bps}bps: Sharpe={r.sharpe_ratio:.3f}, Return={r.total_return:.2f}%"
            )
        except Exception as e:
            print(f"    Dispersion @ {bps}bps: ERROR {e}")
            results.append({"commission_bps": bps, "error": str(e)})
        finally:
            bt.close()

    return results


def run_delta_neutral_sweep() -> list:
    """Sweep commission_bps for delta neutral strategy."""
    results = []
    for bps in COST_LEVELS:
        bt = ResearchBacktester(initial_capital=100_000, commission_bps=bps)
        try:
            signal = DeltaNeutralSignal()
            signal.load_vol_data(bt._get_connection(), "SPY", FIT_START, TEST_END)
            fit_vol = signal._vol_data[signal._vol_data.index <= pd.Timestamp(FIT_END)]
            if len(fit_vol) > 30:
                spread_std = fit_vol["iv_hv_spread"].std()
                signal.entry_threshold = spread_std * 1.0
                signal.exit_threshold = spread_std * 0.3

            test_prices = bt.get_close_prices(["SPY"], TEST_START, TEST_END)
            r = bt.run_daily_signal_strategy(
                signal_fn=signal.generate_signal, prices=test_prices, symbol="SPY"
            )
            results.append(
                {
                    "commission_bps": bps,
                    "sharpe": round(r.sharpe_ratio, 3),
                    "total_return_pct": round(r.total_return, 2),
                    "max_drawdown_pct": round(r.max_drawdown, 2),
                    "num_trades": r.num_trades,
                }
            )
            print(
                f"    Delta Neutral @ {bps}bps: Sharpe={r.sharpe_ratio:.3f}, Return={r.total_return:.2f}%"
            )
        except Exception as e:
            print(f"    Delta Neutral @ {bps}bps: ERROR {e}")
            results.append({"commission_bps": bps, "error": str(e)})
        finally:
            bt.close()

    return results


def run_pairs_sweep() -> list:
    """Sweep commission_bps for pairs trading strategy."""
    results = []
    for bps in COST_LEVELS:
        bt = ResearchBacktester(initial_capital=100_000, commission_bps=bps)
        try:
            full_prices = bt.get_close_prices(["SPY", "IWM"], FIT_START, TEST_END)
            fit_prices = full_prices[full_prices.index <= pd.Timestamp(FIT_END)]

            signal = PairsTradingSignal(lookback=60, entry_z=2.0, exit_z=0.5)
            signal.fit(fit_prices["SPY"], fit_prices["IWM"])

            test_prices = bt.get_close_prices(["SPY", "IWM"], TEST_START, TEST_END)
            r = bt.run_spread_strategy(
                signal_fn=signal.generate_signal, prices=test_prices, symbol_a="SPY", symbol_b="IWM"
            )
            results.append(
                {
                    "commission_bps": bps,
                    "sharpe": round(r.sharpe_ratio, 3),
                    "total_return_pct": round(r.total_return, 2),
                    "max_drawdown_pct": round(r.max_drawdown, 2),
                    "num_trades": r.num_trades,
                }
            )
            print(
                f"    Pairs @ {bps}bps: Sharpe={r.sharpe_ratio:.3f}, Return={r.total_return:.2f}%"
            )
        except Exception as e:
            print(f"    Pairs @ {bps}bps: ERROR {e}")
            results.append({"commission_bps": bps, "error": str(e)})
        finally:
            bt.close()

    return results


def find_breakeven(results: list) -> float:
    """Find approximate breakeven cost (interpolated where Sharpe crosses zero)."""
    for i in range(1, len(results)):
        if "sharpe" not in results[i] or "sharpe" not in results[i - 1]:
            continue
        if results[i - 1]["sharpe"] > 0 and results[i]["sharpe"] <= 0:
            # Linear interpolation
            s1 = results[i - 1]["sharpe"]
            s2 = results[i]["sharpe"]
            c1 = results[i - 1]["commission_bps"]
            c2 = results[i]["commission_bps"]
            return round(c1 + s1 * (c2 - c1) / (s1 - s2), 1)
    # All positive or all negative
    if results and "sharpe" in results[-1]:
        return float("inf") if results[-1]["sharpe"] > 0 else 0.0
    return 0.0


def main():
    print("=" * 60)
    print("  TRANSACTION COST SENSITIVITY ANALYSIS (#541)")
    print("=" * 60)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"  Cost levels: {COST_LEVELS} bps")
    print(f"  Fit: {FIT_START} → {FIT_END}")
    print(f"  Test: {TEST_START} → {TEST_END}")

    all_results = {}

    print("\n  --- Dispersion ---")
    disp = run_dispersion_sweep()
    all_results["dispersion"] = {"results": disp, "breakeven_bps": find_breakeven(disp)}

    print("\n  --- Delta Neutral ---")
    dn = run_delta_neutral_sweep()
    all_results["delta_neutral"] = {"results": dn, "breakeven_bps": find_breakeven(dn)}

    print("\n  --- Pairs Trading (SPY/IWM) ---")
    pairs = run_pairs_sweep()
    all_results["pairs_trading"] = {"results": pairs, "breakeven_bps": find_breakeven(pairs)}

    # Summary
    print(f"\n{'='*60}")
    print("  BREAKEVEN COSTS")
    print(f"{'='*60}")
    for strat, data in all_results.items():
        be = data["breakeven_bps"]
        print(f"    {strat}: {be} bps")

    # Save YAML
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#541",
        "description": "Transaction Cost Sensitivity Analysis",
        "methodology": {
            "cost_levels_bps": COST_LEVELS,
            "strategies": ["dispersion", "delta_neutral", "pairs_trading"],
            "fit_period": f"{FIT_START} to {FIT_END}",
            "test_period": f"{TEST_START} to {TEST_END}",
            "initial_capital": 100_000,
        },
        "results": all_results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / "transaction_cost_results.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")


if __name__ == "__main__":
    main()
