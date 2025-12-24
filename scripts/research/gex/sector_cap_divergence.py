"""
Sector & Cap Divergence Analysis (#499)

Analyze how different market segments behave during GEX regime transitions.
Focus on IWM (small cap) vs SPY (broad) vs DIA (large cap) vs QQQ (tech).

Research questions:
- Cap-weighted divergence during regime transitions
- Sector lead/lag in regime changes
- QQQ (tech) vs DIA (industrials) stability comparison
- Sector divergence as regime transition predictor
"""

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def load_gex_data(db_path: str = ".cache/gex_research.db") -> pd.DataFrame:
    """Load GEX data from SQLite database."""
    conn = sqlite3.connect(db_path)
    query = """
        SELECT symbol, trading_date, regime, underlying_price, asset_class
        FROM options_daily_summary
        WHERE underlying_price IS NOT NULL
        ORDER BY trading_date, symbol
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["trading_date"] = pd.to_datetime(df["trading_date"])

    # Normalize regime names
    regime_map = {"POSITIVE_GAMMA": "POSITIVE", "NEGATIVE_GAMMA": "NEGATIVE", "NEUTRAL": "NEUTRAL"}
    df["regime"] = df["regime"].map(regime_map).fillna("UNKNOWN")

    return df


def classify_regime(regime_str: str) -> str:
    """Normalize regime string."""
    if pd.isna(regime_str):
        return "UNKNOWN"
    return regime_str


def calculate_regime_correlation(df: pd.DataFrame, symbols: list) -> pd.DataFrame:
    """Calculate correlation of regime changes between symbols."""
    # Convert regime to numeric
    regime_map = {"NEGATIVE": -1, "NEUTRAL": 0, "POSITIVE": 1, "UNKNOWN": np.nan}
    df_copy = df.copy()
    df_copy["regime_numeric"] = df_copy["regime"].map(regime_map)

    pivot = df_copy.pivot_table(
        index="trading_date", columns="symbol", values="regime_numeric", aggfunc="first"
    )
    pivot = pivot[[s for s in symbols if s in pivot.columns]]

    return pivot.corr()


def detect_regime_transitions(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Find dates where a symbol's regime changed."""
    symbol_df = df[df["symbol"] == symbol].sort_values("trading_date").copy()
    symbol_df["prev_regime"] = symbol_df["regime"].shift(1)
    symbol_df["transition"] = symbol_df["regime"] != symbol_df["prev_regime"]

    transitions = symbol_df[symbol_df["transition"] & symbol_df["prev_regime"].notna()]
    return transitions[["trading_date", "prev_regime", "regime"]]


def calculate_lead_lag(df: pd.DataFrame, leader: str, follower: str, max_lag: int = 5) -> dict:
    """Calculate lead-lag relationship between two symbols' regime."""
    # Convert regime to numeric
    regime_map = {"NEGATIVE": -1, "NEUTRAL": 0, "POSITIVE": 1, "UNKNOWN": np.nan}
    df_copy = df.copy()
    df_copy["regime_numeric"] = df_copy["regime"].map(regime_map)

    pivot = df_copy.pivot_table(
        index="trading_date", columns="symbol", values="regime_numeric", aggfunc="first"
    )

    if leader not in pivot.columns or follower not in pivot.columns:
        return {"leader": leader, "follower": follower, "best_lag": None}

    leader_regime = pivot[leader].dropna()
    follower_regime = pivot[follower].dropna()

    common_dates = leader_regime.index.intersection(follower_regime.index)
    leader_regime = leader_regime.loc[common_dates]
    follower_regime = follower_regime.loc[common_dates]

    results = {"leader": leader, "follower": follower, "lags": {}}

    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            lagged_leader = leader_regime
            aligned_follower = follower_regime
        elif lag > 0:
            lagged_leader = leader_regime.shift(lag)
            aligned_follower = follower_regime
        else:
            lagged_leader = leader_regime
            aligned_follower = follower_regime.shift(-lag)

        valid = lagged_leader.notna() & aligned_follower.notna()
        if valid.sum() > 30:
            corr, p_val = stats.pearsonr(lagged_leader[valid], aligned_follower[valid])
            results["lags"][lag] = {"correlation": round(corr, 4), "p_value": round(p_val, 6)}

    if results["lags"]:
        best_lag = max(
            results["lags"].keys(),
            key=lambda lag: abs(results["lags"][lag]["correlation"]),
        )
        results["best_lag"] = best_lag
        results["best_correlation"] = results["lags"][best_lag]["correlation"]
        results["best_p_value"] = results["lags"][best_lag]["p_value"]

    return results


def calculate_divergence_metrics(df: pd.DataFrame, symbols: list) -> pd.DataFrame:
    """Calculate daily divergence metrics between symbols."""
    # Pivot regime directly
    regime_df = df.pivot_table(
        index="trading_date", columns="symbol", values="regime", aggfunc="first"
    )
    regime_df = regime_df[[s for s in symbols if s in regime_df.columns]]

    # Count divergence: how many symbols disagree with majority regime
    def count_divergence(row):
        regimes = row.dropna().values
        if len(regimes) == 0:
            return np.nan
        unique, counts = np.unique(regimes, return_counts=True)
        majority = unique[np.argmax(counts)]
        divergent = sum(1 for r in regimes if r != majority)
        return divergent / len(regimes)

    divergence = regime_df.apply(count_divergence, axis=1)

    result = pd.DataFrame({"trading_date": regime_df.index, "divergence_ratio": divergence.values})
    return result


def analyze_transition_prediction(
    df: pd.DataFrame, predictor: str, target: str, lookback: int = 3
) -> dict:
    """Test if predictor's regime changes precede target's regime changes."""
    predictor_transitions = detect_regime_transitions(df, predictor)
    target_transitions = detect_regime_transitions(df, target)

    if predictor_transitions.empty or target_transitions.empty:
        return {"predictor": predictor, "target": target, "predictive_power": None}

    # For each target transition, check if predictor changed in prior N days
    predictions = []
    for _, target_row in target_transitions.iterrows():
        target_date = target_row["trading_date"]
        lookback_start = target_date - pd.Timedelta(days=lookback)

        prior_predictor = predictor_transitions[
            (predictor_transitions["trading_date"] >= lookback_start)
            & (predictor_transitions["trading_date"] < target_date)
        ]

        predicted = len(prior_predictor) > 0
        predictions.append(predicted)

    return {
        "predictor": predictor,
        "target": target,
        "total_transitions": len(predictions),
        "predicted": sum(predictions),
        "predictive_rate": round(sum(predictions) / len(predictions), 3) if predictions else None,
    }


def _report_correlation_section(regime_corr: pd.DataFrame) -> list:
    """Generate regime correlation section."""
    report = []
    report.append("## Regime Correlation Matrix")
    report.append("")
    report.append("Correlation of regime states across market segments:")
    report.append("")

    if not regime_corr.empty:
        symbols = list(regime_corr.columns)
        report.append("| Symbol | " + " | ".join(symbols) + " |")
        report.append("|---|" + "|".join(["---"] * len(symbols)) + "|")
        for sym in symbols:
            row_vals = [
                f"{regime_corr.loc[sym, s]:.2f}" if pd.notna(regime_corr.loc[sym, s]) else "-"
                for s in symbols
            ]
            report.append(f"| {sym} | " + " | ".join(row_vals) + " |")
        report.append("")
    return report


def _report_lead_lag_section(lead_lag_results: list) -> list:
    """Generate lead-lag analysis section."""
    report = []
    report.append("## Lead-Lag Analysis")
    report.append("")
    report.append("Does one segment's GEX predict another's?")
    report.append("")
    report.append("| Leader | Follower | Best Lag | Correlation | P-Value | Significant |")
    report.append("|--------|----------|----------|-------------|---------|-------------|")

    for r in lead_lag_results:
        if r.get("best_lag") is not None:
            sig = "Yes" if r.get("best_p_value", 1) < 0.05 else "No"
            report.append(
                f"| {r['leader']} | {r['follower']} | {r['best_lag']} days | "
                f"{r['best_correlation']:.3f} | {r['best_p_value']:.4f} | {sig} |"
            )
    report.append("")
    return report


def _report_divergence_section(divergence_df: pd.DataFrame) -> list:
    """Generate divergence analysis section."""
    report = []
    report.append("## Regime Divergence Over Time")
    report.append("")

    if not divergence_df.empty:
        mean_div = divergence_df["divergence_ratio"].mean()
        max_div = divergence_df["divergence_ratio"].max()
        high_div_days = (divergence_df["divergence_ratio"] > 0.5).sum()

        report.append(f"- **Mean divergence ratio**: {mean_div:.1%}")
        report.append(f"- **Max divergence ratio**: {max_div:.1%}")
        report.append(f"- **High divergence days (>50%)**: {high_div_days}")
        report.append("")
    return report


def _report_prediction_section(prediction_results: list) -> list:
    """Generate transition prediction section."""
    report = []
    report.append("## Regime Transition Prediction")
    report.append("")
    report.append("Can one segment's regime change predict another's?")
    report.append("")
    report.append("| Predictor | Target | Transitions | Predicted | Rate |")
    report.append("|-----------|--------|-------------|-----------|------|")

    for p in prediction_results:
        if p.get("predictive_rate") is not None:
            report.append(
                f"| {p['predictor']} | {p['target']} | {p['total_transitions']} | "
                f"{p['predicted']} | {p['predictive_rate']:.1%} |"
            )
    report.append("")
    return report


def generate_report(
    regime_corr: pd.DataFrame,
    lead_lag_results: list,
    divergence_df: pd.DataFrame,
    prediction_results: list,
) -> str:
    """Generate markdown report for sector/cap divergence analysis."""
    report = []
    report.append("# Sector & Cap Divergence Analysis")
    report.append("")
    report.append("**Issue**: #499")
    report.append("**Purpose**: Analyze market segment behavior during GEX regime transitions")
    report.append("**Application**: gex-llm-patterns Paper 3 (cross-asset flows)")
    report.append("")

    # Executive Summary
    report.append("## Executive Summary")
    report.append("")

    # Add sections from helper functions
    report.extend(_report_correlation_section(regime_corr))
    report.extend(_report_lead_lag_section(lead_lag_results))
    report.extend(_report_divergence_section(divergence_df))
    report.extend(_report_prediction_section(prediction_results))

    # Interpretation
    report.append("## Interpretation for Paper 3")
    report.append("")
    report.append("### Key Findings")
    report.append("")

    # Analyze IWM vs SPY
    iwm_spy = next(
        (r for r in lead_lag_results if r["leader"] == "IWM" and r["follower"] == "SPY"), None
    )
    if iwm_spy and iwm_spy.get("best_lag") is not None:
        report.append("1. **Small Cap vs Broad Market**:")
        if iwm_spy["best_lag"] == 0:
            report.append("   - IWM and SPY move simultaneously")
        else:
            direction = "leads" if iwm_spy["best_lag"] > 0 else "lags"
            report.append(f"   - IWM {direction} SPY by {abs(iwm_spy['best_lag'])} day(s)")
        report.append("")

    # QQQ vs DIA
    qqq_dia = next(
        (r for r in lead_lag_results if r["leader"] == "QQQ" and r["follower"] == "DIA"), None
    )
    if qqq_dia and qqq_dia.get("best_lag") is not None:
        report.append("2. **Tech vs Industrials**:")
        report.append(f"   - Correlation: {qqq_dia['best_correlation']:.3f}")
        report.append("")

    report.append("### Implications")
    report.append("")
    report.append(
        "1. **Regime Diversity**: Monitor divergence ratio for regime transition warnings"
    )
    report.append("2. **Small Cap Sensitivity**: IWM may provide early warning for broader market")
    report.append(
        "3. **Paper 3 Direction**: Include cap-weighted analysis in cross-asset framework"
    )
    report.append("")
    report.append("---")
    report.append("")
    report.append("Generated by sector_cap_divergence.py")

    return "\n".join(report)


if __name__ == "__main__":
    print("=" * 70)
    print("SECTOR & CAP DIVERGENCE ANALYSIS (#499)")
    print("=" * 70)

    # Load data
    df = load_gex_data()
    print(f"Total records: {len(df):,}")
    print(f"Symbols: {df['symbol'].nunique()}")
    print(f"Date range: {df['trading_date'].min().date()} to {df['trading_date'].max().date()}")

    # Define market segments
    cap_symbols = ["IWM", "SPY", "DIA", "QQQ"]
    available = [s for s in cap_symbols if s in df["symbol"].unique()]
    print(f"\nAnalyzing: {', '.join(available)}")

    # 1. Regime Correlation
    print("\n1. Calculating regime correlations...")
    regime_corr = calculate_regime_correlation(df, available)
    if not regime_corr.empty:
        print(f"  Correlation matrix computed for {len(available)} symbols")

    # 2. Lead-Lag Analysis
    print("\n2. Analyzing lead-lag relationships...")
    lead_lag_results = []
    for leader in available:
        for follower in available:
            if leader != follower:
                result = calculate_lead_lag(df, leader, follower)
                lead_lag_results.append(result)
                if result.get("best_lag") is not None:
                    sig = "*" if result.get("best_p_value", 1) < 0.05 else ""
                    print(
                        f"  {leader} -> {follower}: lag={result['best_lag']}, "
                        f"r={result['best_correlation']:.3f}{sig}"
                    )

    # 3. Divergence Analysis
    print("\n3. Calculating regime divergence...")
    divergence_df = calculate_divergence_metrics(df, available)
    print(f"  Mean divergence: {divergence_df['divergence_ratio'].mean():.1%}")

    # 4. Transition Prediction
    print("\n4. Testing regime transition prediction...")
    prediction_results = []
    for predictor in available:
        for target in available:
            if predictor != target:
                result = analyze_transition_prediction(df, predictor, target)
                prediction_results.append(result)
                if result.get("predictive_rate") is not None:
                    print(f"  {predictor} -> {target}: {result['predictive_rate']:.1%}")

    # Generate report
    report = generate_report(regime_corr, lead_lag_results, divergence_df, prediction_results)

    # Save report
    report_path = Path("docs/08_research/02_gex_research/sector_cap_divergence.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"\n[OK] Report saved: {report_path}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    significant = [r for r in lead_lag_results if r.get("best_p_value", 1) < 0.05]
    print(f"Significant lead-lag relationships: {len(significant)}/{len(lead_lag_results)}")

    predictive = [p for p in prediction_results if (p.get("predictive_rate") or 0) > 0.3]
    print(f"Predictive relationships (>30%): {len(predictive)}/{len(prediction_results)}")

    print("\nKey takeaway for Paper 3:")
    if significant:
        print("  -> Cap divergence provides additional cross-asset signal")
    else:
        print("  -> Cap segments move together - limited predictive value")
