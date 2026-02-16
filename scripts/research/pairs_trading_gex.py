"""
Pairs Trading Mean Reversion with GEX Regime Overlay (#546).

Research runner that compares baseline pairs trading (pure z-score)
against GEX-enhanced (regime-filtered) on real equity prices from PostgreSQL.

Pairs: (SPY, IWM), (QQQ, SPY) — validated in test_gex_research_data_access.py.
Data: equity_prices_daily (2020-2026), options_daily_summary regime (2020-2025).

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/pairs_trading_gex.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import yaml

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import ResearchBacktester
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


PAIRS = [("SPY", "IWM"), ("QQQ", "SPY")]
# Fit on 2020-2021, test on 2022-2023 (regime-diverse: 76% bearish_gamma in 2022)
FIT_START = "2020-01-02"
FIT_END = "2021-12-31"
TEST_START = "2022-01-03"
TEST_END = "2023-12-29"

RESULTS_DIR = Path("docs/08_research/03_gex_research")


def run_pair_experiment(
    bt: ResearchBacktester,
    sym_a: str,
    sym_b: str,
    fit_start: str,
    fit_end: str,
    test_start: str,
    test_end: str,
) -> dict:
    """Run baseline and GEX-enhanced backtest for one pair."""
    print(f"\n{'='*60}")
    print(f"  Pair: {sym_a} / {sym_b}")
    print(f"  Fit:  {fit_start} → {fit_end}")
    print(f"  Test: {test_start} → {test_end}")
    print(f"{'='*60}")

    # 1. Fetch prices
    symbols = [sym_a, sym_b]
    fit_prices = bt.get_close_prices(symbols, fit_start, fit_end)
    test_prices = bt.get_close_prices(symbols, test_start, test_end)

    print(f"  Fit period:  {len(fit_prices)} days")
    print(f"  Test period: {len(test_prices)} days")

    if len(fit_prices) < 120 or len(test_prices) < 60:
        print("  ⚠ Insufficient data, skipping pair")
        return {}

    # 2. Fit model on in-sample period
    signal = PairsTradingSignal(lookback=60, entry_z=2.0, exit_z=0.5)
    fit_result = signal.fit(fit_prices[sym_a], fit_prices[sym_b])

    print("\n  Cointegration Results:")
    print(f"    Hedge ratio (β):    {fit_result['hedge_ratio']:.4f}")
    print(f"    Coint p-value:      {fit_result['coint_pvalue']:.4f}")
    print(f"    ADF p-value:        {fit_result['adf_pvalue']:.4f}")
    print(f"    Half-life:          {fit_result['half_life_days']:.1f} days")
    print(f"    R²:                 {fit_result['r_squared']:.4f}")
    print(f"    Cointegrated:       {'YES' if fit_result['is_cointegrated'] else 'NO'}")

    # 3. Baseline backtest (pure z-score)
    print("\n  Running BASELINE backtest...")
    baseline_results = bt.run_spread_strategy(
        signal_fn=signal.generate_signal,
        prices=test_prices,
        symbol_a=sym_a,
        symbol_b=sym_b,
    )
    print(f"    Sharpe:   {baseline_results.sharpe_ratio:.3f}")
    print(f"    Return:   {baseline_results.total_return:.2f}%")
    print(f"    Drawdown: {baseline_results.max_drawdown:.2f}%")
    print(f"    Trades:   {baseline_results.num_trades}")

    # 4. GEX-enhanced backtest
    print("\n  Running GEX-ENHANCED backtest...")
    overlay = bt.get_gex_overlay()

    def gex_filtered_signal(prices_df, idx):
        """Wrap signal with GEX regime filter."""
        base = signal.generate_signal(prices_df, idx)
        date = prices_df.index[idx]

        regime = overlay.get_regime(sym_a, date)
        scale = overlay.position_scale(sym_a, date)

        if base["action"] in ("BUY", "SELL") and scale < 0.5:
            # Suppress entry in weak regimes
            base["action"] = "HOLD"
            base["position_size"] = 0.0
            base["reasoning"] += f" [GEX suppressed: {regime}, scale={scale:.2f}]"
        elif base["action"] in ("BUY", "SELL"):
            base["position_size"] *= scale
            base["reasoning"] += f" [GEX: {regime}, scale={scale:.2f}]"

        return base

    gex_results = bt.run_spread_strategy(
        signal_fn=gex_filtered_signal,
        prices=test_prices,
        symbol_a=sym_a,
        symbol_b=sym_b,
    )
    print(f"    Sharpe:   {gex_results.sharpe_ratio:.3f}")
    print(f"    Return:   {gex_results.total_return:.2f}%")
    print(f"    Drawdown: {gex_results.max_drawdown:.2f}%")
    print(f"    Trades:   {gex_results.num_trades}")

    # 5. Regime distribution during test period
    regime_counts = {"bullish_gamma": 0, "bearish_gamma": 0, "neutral": 0, "unknown": 0}
    for date in test_prices.index:
        r = overlay.get_regime(sym_a, date)
        regime_counts[r if r else "unknown"] += 1

    print("\n  Regime distribution (test period):")
    for r, c in regime_counts.items():
        print(f"    {r}: {c} days ({c/len(test_prices)*100:.1f}%)")

    # 6. Improvement
    sharpe_diff = gex_results.sharpe_ratio - baseline_results.sharpe_ratio
    print(f"\n  Sharpe improvement: {sharpe_diff:+.3f}")

    return {
        "pair": f"{sym_a}/{sym_b}",
        "fit_period": f"{fit_start} to {fit_end}",
        "test_period": f"{test_start} to {test_end}",
        "cointegration": {
            "hedge_ratio": round(fit_result["hedge_ratio"], 4),
            "coint_pvalue": round(fit_result["coint_pvalue"], 4),
            "adf_pvalue": round(fit_result["adf_pvalue"], 4),
            "half_life_days": round(fit_result["half_life_days"], 1),
            "r_squared": round(fit_result["r_squared"], 4),
            "is_cointegrated": fit_result["is_cointegrated"],
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
    print("  PAIRS TRADING MEAN REVERSION — GEX REGIME OVERLAY (#546)")
    print("=" * 60)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"  Pairs: {PAIRS}")
    print(f"  Fit:  {FIT_START} → {FIT_END}")
    print(f"  Test: {TEST_START} → {TEST_END}")

    bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)

    all_results = []
    for sym_a, sym_b in PAIRS:
        try:
            result = run_pair_experiment(bt, sym_a, sym_b, FIT_START, FIT_END, TEST_START, TEST_END)
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"\n  ✗ Error on {sym_a}/{sym_b}: {e}")

    bt.close()

    if not all_results:
        print("\nNo results produced. Check database connectivity.")
        return

    # Build YAML output
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#546",
        "description": "Pairs Trading Mean Reversion with GEX Regime Overlay",
        "methodology": {
            "strategy": "Cointegration-based pairs trading (Engle-Granger)",
            "fit_period": f"{FIT_START} to {FIT_END}",
            "test_period": f"{TEST_START} to {TEST_END}",
            "pairs": [[a, b] for a, b in PAIRS],
            "entry_threshold": "2.0 sigma",
            "exit_threshold": "0.5 sigma",
            "lookback": "60 days",
            "hedge_ratio": "OLS on log prices",
            "gex_overlay": "options_daily_summary.regime (bullish_gamma, bearish_gamma, neutral)",
        },
        "results": all_results,
        "causal_mechanisms": {
            "gex_regime_filter": {
                "who": "Dealer gamma hedging (market makers)",
                "whom": "Mean-reverting spread dynamics between correlated ETFs",
                "what": "Persistent GEX regimes indicate stable dealer hedging flows, "
                "supporting mean reversion. Transitional regimes imply hedging "
                "flow disruption, weakening mean reversion assumptions.",
                "evidence": [
                    "Bullish gamma regimes show dealer hedging that dampens volatility",
                    "Spread half-life should be shorter in persistent regimes",
                    "Trade suppression in neutral/transitional avoids false signals",
                ],
            }
        },
    }

    # Save YAML
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / "pairs_trading_results.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")

    # Summary table
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Pair':<12} {'Base Sharpe':>12} {'GEX Sharpe':>12} {'Δ Sharpe':>10}")
    print(f"  {'-'*46}")
    for r in all_results:
        print(
            f"  {r['pair']:<12} "
            f"{r['baseline']['sharpe_ratio']:>12.3f} "
            f"{r['gex_enhanced']['sharpe_ratio']:>12.3f} "
            f"{r['sharpe_improvement']:>+10.3f}"
        )


if __name__ == "__main__":
    main()
