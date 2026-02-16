"""
MACD+RSI in Positive Gamma Re-validation (#531).

Tests whether MACD(13/34/8) + RSI(14/30/70) consensus signals perform better
in bullish_gamma regimes (dealers long gamma → smoother trends → better for
trend-following indicators).

Corrected methodology:
- shift(1) applied to prevent look-ahead bias
- Turnover-proportional costs (2 bps)
- Reports median alongside mean
- Welch's t-test for statistical significance

Usage:
    ~/miniconda3/envs/AutoGex/bin/python scripts/research/macd_rsi_regime_analysis.py
"""

import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.backtesting.research_backtester import ResearchBacktester
from src.backtesting.signals.macd_rsi_signal import MACDRSISignal


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
TEST_START = "2021-01-04"
TEST_END = "2023-12-29"
WARMUP_START = "2020-01-02"
RESULTS_DIR = Path("docs/08_research/03_gex_research")


def analyze_symbol(bt: ResearchBacktester, symbol: str) -> dict:
    """Run MACD+RSI analysis for one symbol, stratified by GEX regime."""
    print(f"\n  --- {symbol} ---")

    # Fetch full prices (warmup + test)
    prices = bt.get_close_prices([symbol], WARMUP_START, TEST_END)
    if len(prices) < 200:
        print(f"  Insufficient data ({len(prices)} days)")
        return {}

    print(f"  Total days: {len(prices)}")

    # Run full backtest (warmup data for indicators included via full prices)
    full_signal = MACDRSISignal()
    results = bt.run_daily_signal_strategy(
        signal_fn=full_signal.generate_signal, prices=prices, symbol=symbol
    )
    print(
        f"  Full period Sharpe: {results.sharpe_ratio:.3f}, "
        f"Return: {results.total_return:.2f}%, Trades: {results.num_trades}"
    )

    # Stratify returns by regime
    overlay = bt.get_gex_overlay()
    import importlib.util as _ilu

    _ip = Path(__file__).parent.parent.parent / "src" / "trading" / "instruments" / "indicators.py"
    _sp = _ilu.spec_from_file_location("indicators", _ip)
    _im = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_im)
    calculate_macd, calculate_rsi, calculate_voting_consensus = (
        _im.calculate_macd,
        _im.calculate_rsi,
        _im.calculate_voting_consensus,
    )

    price_series = prices[symbol]
    daily_returns = price_series.pct_change()

    macd_data = calculate_macd(price_series)
    rsi_data = calculate_rsi(price_series)
    voting = calculate_voting_consensus(macd_data, rsi_data)
    consensus = voting["consensus"].shift(1).fillna(False)

    # For each test day: regime + whether signal was active + return
    regime_returns = {"bullish_gamma": [], "bearish_gamma": [], "neutral": [], "all": []}
    regime_signal_returns = {"bullish_gamma": [], "bearish_gamma": [], "neutral": []}

    test_mask = prices.index >= pd.Timestamp(TEST_START)
    for i in range(len(prices)):
        if not test_mask[i]:
            continue
        date = prices.index[i]
        ret = daily_returns.iloc[i]
        if np.isnan(ret):
            continue

        regime = overlay.get_regime(symbol, date)
        if regime not in regime_returns:
            continue

        regime_returns[regime].append(ret)
        regime_returns["all"].append(ret)

        # Signal-conditional return: return when indicator says BUY
        if bool(consensus.iloc[i]):
            regime_signal_returns[regime].append(ret)

    # Calculate per-regime metrics
    regime_metrics = {}
    for regime in ["bullish_gamma", "bearish_gamma", "neutral"]:
        rets = regime_returns[regime]
        sig_rets = regime_signal_returns[regime]
        if len(rets) < 10:
            print(f"    {regime}: {len(rets)} days (insufficient)")
            continue

        s = pd.Series(rets)
        sig_s = pd.Series(sig_rets) if sig_rets else pd.Series(dtype=float)

        sharpe = float(np.sqrt(252) * s.mean() / s.std()) if s.std() > 0 else 0.0
        sig_sharpe = (
            float(np.sqrt(252) * sig_s.mean() / sig_s.std())
            if len(sig_s) > 1 and sig_s.std() > 0
            else 0.0
        )

        regime_metrics[regime] = {
            "n_days": len(rets),
            "n_signal_days": len(sig_rets),
            "mean_return": round(float(s.mean()), 6),
            "median_return": round(float(s.median()), 6),
            "std_return": round(float(s.std()), 6),
            "sharpe_ratio": round(sharpe, 3),
            "signal_sharpe": round(sig_sharpe, 3),
            "win_rate": round(float((s > 0).mean()) * 100, 1),
            "max_drawdown": round(float(s.min()), 4),
        }
        print(
            f"    {regime}: {len(rets)} days, Sharpe={sharpe:.3f}, "
            f"signal_Sharpe={sig_sharpe:.3f}, win={float((s > 0).mean())*100:.1f}%"
        )

    # Welch's t-test: bullish vs bearish returns
    t_test = None
    bull_rets = regime_returns.get("bullish_gamma", [])
    bear_rets = regime_returns.get("bearish_gamma", [])
    if len(bull_rets) > 10 and len(bear_rets) > 10:
        t_stat, p_val = sp_stats.ttest_ind(bull_rets, bear_rets, equal_var=False)
        t_test = {"t_statistic": round(float(t_stat), 3), "p_value": round(float(p_val), 4)}
        print(f"    Welch t-test (bull vs bear): t={t_stat:.3f}, p={p_val:.4f}")

    # Sharpe difference
    bull_sharpe = regime_metrics.get("bullish_gamma", {}).get("sharpe_ratio", 0)
    bear_sharpe = regime_metrics.get("bearish_gamma", {}).get("sharpe_ratio", 0)
    sharpe_diff = bull_sharpe - bear_sharpe

    return {
        "symbol": symbol,
        "full_sharpe": round(results.sharpe_ratio, 3),
        "full_return_pct": round(results.total_return, 2),
        "num_trades": results.num_trades,
        "by_regime": regime_metrics,
        "welch_t_test": t_test,
        "sharpe_diff_bull_minus_bear": round(sharpe_diff, 3),
    }


def main():
    print("=" * 60)
    print("  MACD+RSI IN POSITIVE GAMMA RE-VALIDATION (#531)")
    print("=" * 60)
    print(f"  Timestamp: {datetime.datetime.now().isoformat()}")
    print(f"  Test: {TEST_START} → {TEST_END}")

    bt = ResearchBacktester(initial_capital=100_000, commission_bps=2.0)
    results = []

    try:
        for symbol in SYMBOLS:
            r = analyze_symbol(bt, symbol)
            if r:
                results.append(r)
    except Exception as e:
        print(f"\n  Error: {e}")
        import traceback

        traceback.print_exc()

    bt.close()

    if not results:
        print("\nNo results.")
        return

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY: MACD+RSI Sharpe by Regime")
    print(f"{'='*60}")
    for r in results:
        sd = r.get("sharpe_diff_bull_minus_bear", 0)
        print(f"  {r['symbol']}: Sharpe diff (bullish - bearish) = {sd:+.3f}")

    # Save YAML
    output = {
        "run_timestamp": datetime.datetime.now().isoformat(),
        "issue": "#531",
        "description": "MACD+RSI in Positive Gamma Re-validation",
        "methodology": {
            "strategy": "MACD(13/34/8) + RSI(14/30/70) voting consensus",
            "look_ahead_prevention": "shift(1) applied to signal series",
            "commission": "2 bps turnover-proportional",
            "test_period": f"{TEST_START} to {TEST_END}",
            "warmup_from": WARMUP_START,
            "symbols": SYMBOLS,
            "regime_source": "options_daily_summary.regime",
            "statistical_test": "Welch's t-test (unequal variance)",
        },
        "results": results,
        "hypothesis": "MACD+RSI performs better in bullish_gamma (Sharpe diff > 0.2)",
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    yaml_path = RESULTS_DIR / "macd_rsi_regime_results.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(_to_native(output), f, default_flow_style=False, sort_keys=False, width=100)
    print(f"\n  Results saved to {yaml_path}")


if __name__ == "__main__":
    main()
