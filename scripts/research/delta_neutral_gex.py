"""
Delta Neutral / Long Volatility with GEX Regime Overlay (#544).

Research runner that compares baseline volatility trading (IV-RV spread)
against GEX-enhanced (regime-conditional sizing) on real data from PostgreSQL.

Data: options_daily_summary IV-HV spreads (2020-2025, 1505 SPY trading days).

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/delta_neutral_gex.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.signals.delta_neutral_signal import DeltaNeutralSignal


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


SYMBOLS = ["SPY"]
# Fit on 2020-2021, test on 2022-2023 (regime-diverse: 76% bearish_gamma in 2022)
FIT_START = "2020-01-02"
FIT_END = "2021-12-31"
TEST_START = "2022-01-03"
TEST_END = "2023-12-29"

RESULTS_DIR = Path("docs/08_research/03_gex_research")


def run_delta_neutral_experiment(  # noqa: C901
    bt: ResearchBacktester,
    symbol: str,
    fit_start: str,
    fit_end: str,
    test_start: str,
    test_end: str,
) -> dict:
    """Run baseline and GEX-enhanced delta neutral backtest."""
    print(f"\n{'='*60}")
    print(f"  Delta Neutral: {symbol}")
    print(f"  Fit:  {fit_start} → {fit_end}")
    print(f"  Test: {test_start} → {test_end}")
    print(f"{'='*60}")

    conn = bt._get_connection()

    # 1. Load vol data for fit period (parameter estimation)
    fit_signal = DeltaNeutralSignal(
        vol_spread_window=30, entry_threshold=0.02, exit_threshold=0.005
    )
    fit_signal.load_vol_data(conn, symbol, fit_start, fit_end)
    fit_stats = fit_signal.calculate_spread_stats()

    print(f"\n  In-sample IV-RV spread stats ({fit_start} to {fit_end}):")
    print(f"    Mean:           {fit_stats['mean']:.4f}")
    print(f"    Std:            {fit_stats['std']:.4f}")
    print(f"    Min/Max:        {fit_stats['min']:.4f} / {fit_stats['max']:.4f}")
    print(f"    % positive:     {fit_stats['pct_positive']:.1f}%")
    print(f"    % > entry:      {fit_stats['pct_above_entry']:.1f}%")
    print(f"    % < -entry:     {fit_stats['pct_below_neg_entry']:.1f}%")

    # Use in-sample stats to set adaptive thresholds
    # Entry at 1 std above/below mean
    adaptive_entry = fit_stats["std"]
    adaptive_exit = fit_stats["std"] * 0.25
    print("\n  Adaptive thresholds (from IS stats):")
    print(f"    Entry: ±{adaptive_entry:.4f}")
    print(f"    Exit:  ±{adaptive_exit:.4f}")

    # 2. Set up test signal with adaptive thresholds
    test_signal = DeltaNeutralSignal(
        vol_spread_window=30,
        entry_threshold=adaptive_entry,
        exit_threshold=adaptive_exit,
    )
    test_signal.load_vol_data(conn, symbol, test_start, test_end)
    test_stats = test_signal.calculate_spread_stats()

    print(f"\n  Out-of-sample IV-RV spread stats ({test_start} to {test_end}):")
    print(f"    Mean:           {test_stats['mean']:.4f}")
    print(f"    Std:            {test_stats['std']:.4f}")
    print(f"    % > entry:      {test_stats['pct_above_entry']:.1f}%")
    print(f"    % < -entry:     {test_stats['pct_below_neg_entry']:.1f}%")

    # 3. Fetch equity prices for test period
    test_prices = bt.get_close_prices([symbol], test_start, test_end)
    if len(test_prices) < 100:
        print("  ⚠ Insufficient price data, skipping")
        return {}

    # 4. Baseline backtest
    print("\n  Running BASELINE backtest...")
    baseline_results = bt.run_daily_signal_strategy(
        signal_fn=test_signal.generate_signal,
        prices=test_prices,
        symbol=symbol,
    )
    print(f"    Sharpe:   {baseline_results.sharpe_ratio:.3f}")
    print(f"    Return:   {baseline_results.total_return:.2f}%")
    print(f"    Drawdown: {baseline_results.max_drawdown:.2f}%")
    print(f"    Trades:   {baseline_results.num_trades}")

    # 5. GEX-enhanced backtest
    print("\n  Running GEX-ENHANCED backtest...")
    overlay = bt.get_gex_overlay()

    def gex_filtered_signal(prices_df, idx):
        """Wrap signal with GEX regime logic for delta neutral.

        Key insight: In bearish gamma (negative GEX), dealers hedge by
        amplifying moves → favor long vol. In bullish gamma, dealers dampen
        moves → favor short vol.
        """
        base = test_signal.generate_signal(prices_df, idx)
        date = prices_df.index[idx]
        regime = overlay.get_regime(symbol, date)
        _scale = overlay.position_scale(symbol, date)

        if base["action"] == "BUY":
            # Long vol: size up in bearish gamma (volatility expansion)
            if regime == "bearish_gamma":
                base["position_size"] = min(1.5, base["position_size"] * 1.5)
                base["reasoning"] += f" [GEX boost: {regime}]"
            elif regime == "neutral":
                base["position_size"] *= 0.5
                base["reasoning"] += f" [GEX reduce: {regime}]"
        elif base["action"] == "SELL":
            # Short vol: size up in bullish gamma (volatility compression)
            if regime == "bullish_gamma":
                base["position_size"] = min(1.5, base["position_size"] * 1.25)
                base["reasoning"] += f" [GEX boost: {regime}]"
            elif regime == "bearish_gamma":
                # Don't sell vol in bearish gamma — suppress
                base["action"] = "HOLD"
                base["position_size"] = 0.0
                base["reasoning"] += f" [GEX suppress short-vol in {regime}]"

        return base

    gex_results = bt.run_daily_signal_strategy(
        signal_fn=gex_filtered_signal,
        prices=test_prices,
        symbol=symbol,
    )
    print(f"    Sharpe:   {gex_results.sharpe_ratio:.3f}")
    print(f"    Return:   {gex_results.total_return:.2f}%")
    print(f"    Drawdown: {gex_results.max_drawdown:.2f}%")
    print(f"    Trades:   {gex_results.num_trades}")

    # 6. Regime distribution
    regime_counts = {"bullish_gamma": 0, "bearish_gamma": 0, "neutral": 0, "unknown": 0}
    for date in test_prices.index:
        r = overlay.get_regime(symbol, date)
        regime_counts[r if r else "unknown"] += 1

    print("\n  Regime distribution (test period):")
    for r, c in regime_counts.items():
        print(f"    {r}: {c} days ({c/len(test_prices)*100:.1f}%)")

    sharpe_diff = gex_results.sharpe_ratio - baseline_results.sharpe_ratio
    print(f"\n  Sharpe improvement: {sharpe_diff:+.3f}")

    return {
        "symbol": symbol,
        "fit_period": f"{fit_start} to {fit_end}",
        "test_period": f"{test_start} to {test_end}",
        "in_sample_spread_stats": fit_stats,
        "out_of_sample_spread_stats": test_stats,
        "adaptive_thresholds": {
            "entry": round(adaptive_entry, 4),
            "exit": round(adaptive_exit, 4),
        },
        "baseline": {
            "sharpe_ratio": round(baseline_results.sharpe_ratio, 3),
            "total_return_pct": round(baseline_results.total_return, 2),
            "max_drawdown_pct": round(baseline_results.max_drawdown, 2),
            "win_rate_pct": round(baseline_results.win_rate, 1),
            "num_trades": baseline_results.num_trades,
            "volatility_pct": round(baseline_results.volatility, 2),
        },
        "gex_enhanced": {
            "sharpe_ratio": round(gex_results.sharpe_ratio, 3),
            "total_return_pct": round(gex_results.total_return, 2),
            "max_drawdown_pct": round(gex_results.max_drawdown, 2),
            "win_rate_pct": round(gex_results.win_rate, 1),
            "num_trades": gex_results.num_trades,
            "volatility_pct": round(gex_results.volatility, 2),
        },
        "sharpe_improvement": round(sharpe_diff, 3),
        "regime_distribution": regime_counts,
    }


def main():
    print("=" * 60)
    print("  DELTA NEUTRAL / LONG VOLATILITY — GEX REGIME OVERLAY (#544)")
    print("=" * 60)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")

    bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)

    all_results = []
    for symbol in SYMBOLS:
        try:
            result = run_delta_neutral_experiment(
                bt, symbol, FIT_START, FIT_END, TEST_START, TEST_END
            )
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"\n  ✗ Error on {symbol}: {e}")
            import traceback

            traceback.print_exc()

    bt.close()

    if not all_results:
        print("\nNo results produced.")
        return

    # Save YAML
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#544",
        "description": "Delta Neutral / Long Volatility with GEX Regime Overlay",
        "methodology": {
            "strategy": "IV-RV spread mean reversion",
            "data_source": "options_daily_summary (iv_hv_spread_30, hv_30, realized_vol_30)",
            "fit_period": f"{FIT_START} to {FIT_END}",
            "test_period": f"{TEST_START} to {TEST_END}",
            "entry_threshold": "Adaptive (1 std of IS spread)",
            "exit_threshold": "Adaptive (0.25 std of IS spread)",
            "pnl_model": "Simplified: spread_change * 5.0 scaling factor",
            "gex_overlay": "Regime-conditional sizing (bearish_gamma → boost long vol, bullish_gamma → boost short vol)",
        },
        "results": all_results,
        "causal_mechanisms": {
            "gex_regime_filter": {
                "who": "Dealer gamma hedging (market makers)",
                "whom": "Implied vs realized volatility dynamics",
                "what": "In negative gamma (bearish) regimes, dealers hedge by buying vol → "
                "amplifies moves → benefits long vol. In positive gamma (bullish) "
                "regimes, dealers sell vol to hedge → dampens moves → benefits short vol.",
                "evidence": [
                    "Bearish gamma regimes historically show higher realized vol",
                    "Bullish gamma regimes show compressed realized vol (dealer dampening)",
                    "IV-RV spread tends to be negative in bearish gamma (vol underpriced)",
                ],
            }
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / "delta_neutral_results.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")


if __name__ == "__main__":
    main()
