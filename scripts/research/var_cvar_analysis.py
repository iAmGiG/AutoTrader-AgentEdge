"""
VaR vs CVaR Risk Metrics Analysis with GEX Regime Stratification (#543).

Compares historical VaR, CVaR (Expected Shortfall), parametric VaR, and
Cornish-Fisher VaR across GEX regimes. Tests whether bearish_gamma regimes
exhibit fatter tails (higher ES/VaR ratio) than bullish_gamma.

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/var_cvar_analysis.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.risk_metrics import calculate_all_risk_metrics


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


SYMBOLS = ["SPY", "QQQ", "IWM"]
START = "2020-01-02"
END = "2023-12-29"
LOOKBACKS = [20, 60, 120, 252]
RESULTS_DIR = Path("docs/08_research/03_gex_research")


def run_var_cvar_analysis(bt: ResearchBacktester) -> dict:
    """Run VaR vs CVaR analysis stratified by GEX regime."""
    print(f"\n{'='*60}")
    print("  VaR vs CVaR — GEX Regime Stratification (#543)")
    print(f"  Period: {START} → {END}")
    print(f"{'='*60}")

    overlay = bt.get_gex_overlay()
    results_by_symbol = {}

    for symbol in SYMBOLS:
        print(f"\n  --- {symbol} ---")
        prices = bt.get_close_prices([symbol], START, END)
        if len(prices) < 100:
            print(f"  Insufficient data for {symbol}, skipping")
            continue

        returns = prices[symbol].pct_change().dropna()
        print(f"  Total returns: {len(returns)} days")

        # Full-sample metrics
        full_metrics = calculate_all_risk_metrics(returns)
        print(
            f"  Full sample: VaR={full_metrics['historical_var']:.4f}, "
            f"CVaR={full_metrics['cvar']:.4f}, "
            f"ES/VaR={full_metrics['es_var_ratio']}"
        )

        # Regime-stratified
        regime_returns = {"bullish_gamma": [], "bearish_gamma": [], "neutral": []}
        for date, ret in returns.items():
            regime = overlay.get_regime(symbol, date)
            if regime in regime_returns:
                regime_returns[regime].append(ret)

        regime_metrics = {}
        for regime, rets in regime_returns.items():
            if len(rets) < 20:
                print(f"    {regime}: {len(rets)} days (insufficient)")
                continue
            s = pd.Series(rets)
            m = calculate_all_risk_metrics(s)
            regime_metrics[regime] = m
            print(
                f"    {regime}: {len(rets)} days, VaR={m['historical_var']:.4f}, "
                f"CVaR={m['cvar']:.4f}, ES/VaR={m['es_var_ratio']}"
            )

        # Lookback sensitivity
        lookback_results = {}
        for lb in LOOKBACKS:
            if len(returns) < lb:
                continue
            recent = returns.iloc[-lb:]
            m = calculate_all_risk_metrics(recent)
            lookback_results[f"{lb}d"] = m
            print(
                f"    Lookback {lb}d: VaR={m['historical_var']:.4f}, "
                f"CVaR={m['cvar']:.4f}, ES/VaR={m['es_var_ratio']}"
            )

        results_by_symbol[symbol] = {
            "full_sample": full_metrics,
            "by_regime": regime_metrics,
            "by_lookback": lookback_results,
            "n_days": len(returns),
        }

    return results_by_symbol


def main():
    print("=" * 60)
    print("  VAR vs CVAR RISK METRICS — GEX REGIME ANALYSIS (#543)")
    print("=" * 60)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")

    bt = ResearchBacktester(initial_capital=100_000)

    try:
        results = run_var_cvar_analysis(bt)
    except Exception as e:
        print(f"\n  Error: {e}")
        import traceback

        traceback.print_exc()
        results = {}

    bt.close()

    if not results:
        print("\nNo results produced.")
        return

    # Key findings
    print(f"\n{'='*60}")
    print("  KEY FINDINGS")
    print(f"{'='*60}")

    for sym, data in results.items():
        regimes = data.get("by_regime", {})
        bull = regimes.get("bullish_gamma", {})
        bear = regimes.get("bearish_gamma", {})
        if bull and bear:
            bull_ratio = bull.get("es_var_ratio")
            bear_ratio = bear.get("es_var_ratio")
            if bull_ratio and bear_ratio:
                print(
                    f"  {sym}: ES/VaR bullish={bull_ratio:.3f}, "
                    f"bearish={bear_ratio:.3f}, "
                    f"diff={bear_ratio - bull_ratio:+.3f}"
                )

    # Save YAML
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#543",
        "description": "VaR vs CVaR Risk Metrics with GEX Regime Stratification",
        "methodology": {
            "metrics": [
                "Historical VaR",
                "CVaR (Expected Shortfall)",
                "Parametric VaR",
                "Cornish-Fisher VaR",
                "ES/VaR ratio",
            ],
            "confidence": "95%",
            "symbols": SYMBOLS,
            "period": f"{START} to {END}",
            "lookbacks": LOOKBACKS,
            "regime_source": "options_daily_summary.regime",
        },
        "results": results,
        "causal_mechanisms": {
            "regime_tail_risk": {
                "who": "Dealer gamma hedging",
                "whom": "Return distribution tails",
                "what": "In bearish gamma, dealer hedging amplifies moves → fatter tails → "
                "higher ES/VaR ratio. VaR alone understates risk in these regimes.",
                "evidence": [
                    "ES/VaR ratio should be > 1.26 in bearish_gamma (fat tails)",
                    "Cornish-Fisher VaR > Parametric VaR when skewness/kurtosis are non-zero",
                    "Lookback sensitivity reveals regime-dependent risk dynamics",
                ],
            }
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / "var_cvar_results.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")


if __name__ == "__main__":
    main()
