#!/usr/bin/env python3
"""
Analyze performance of scan results from cached data.
"""

import os
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict


def analyze_scan_results():
    """Analyze all available scan results."""

    scan_dir = Path(".cache/daily_scans")

    # Collect all scan data
    all_scans = []
    signal_counts = defaultdict(int)
    approved_counts = defaultdict(int)

    print("\n" + "=" * 80)
    print("MECHANICAL STRATEGY PERFORMANCE ANALYSIS")
    print("=" * 80)

    # Read all CSV files
    csv_files = sorted(scan_dir.glob("scan_*.csv"))
    csv_files = [f for f in csv_files if "_summary" not in str(f)]

    print(f"\nAnalyzing {len(csv_files)} scan files...")

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)

        # Count signals per symbol
        for _, row in df.iterrows():
            if row["TA_Signal"] in ["BUY", "SELL"]:
                signal_counts[row["Symbol"]] += 1
                if row["Approved"] == "YES":
                    approved_counts[row["Symbol"]] += 1

                all_scans.append({
                    "date": row["Date"],
                    "symbol": row["Symbol"],
                    "signal": row["TA_Signal"],
                    "strength": row["Signal_Strength"],
                    "market_heat": row["Market_Heat"],
                    "approved": row["Approved"]
                })

    # Convert to DataFrame for analysis
    scan_df = pd.DataFrame(all_scans)

    if scan_df.empty:
        print("\nNo trading signals found in scan results.")
        return

    # 1. Overall Statistics
    print("\n1. OVERALL STATISTICS:")
    print(f"   Total Signals: {len(scan_df)}")
    print(f"   Approved Trades: {len(scan_df[scan_df['approved'] == 'YES'])}")
    print(
        f"   Approval Rate: {len(scan_df[scan_df['approved'] == 'YES']) / len(scan_df) * 100:.1f}%")
    print(f"   Date Range: {scan_df['date'].min()} to {scan_df['date'].max()}")

    # 2. Market Heat Analysis
    print("\n2. MARKET HEAT ANALYSIS:")
    heat_stats = scan_df.groupby('market_heat')['approved'].apply(
        lambda x: (x == 'YES').sum() / len(x) * 100
    )
    print("   Heat Level -> Approval Rate:")
    for heat, rate in heat_stats.items():
        print(f"   {heat:>6.2f} -> {rate:>5.1f}%")

    # 3. Symbol Performance
    print("\n3. TOP PERFORMING SYMBOLS:")
    symbol_df = pd.DataFrame([
        {
            "symbol": symbol,
            "total_signals": count,
            "approved_signals": approved_counts.get(symbol, 0),
            "approval_rate": approved_counts.get(symbol, 0) / count * 100
        }
        for symbol, count in signal_counts.items()
    ])

    symbol_df = symbol_df.sort_values("total_signals", ascending=False)

    for _, row in symbol_df.head(10).iterrows():
        print(f"   {row['symbol']:>6}: {row['total_signals']:>2} signals, "
              f"{row['approved_signals']:>2} approved ({row['approval_rate']:>5.1f}%)")

    # 4. Daily Signal Distribution
    print("\n4. DAILY SIGNAL DISTRIBUTION:")
    daily_signals = scan_df.groupby('date').size()
    daily_approved = scan_df[scan_df['approved'] == 'YES'].groupby('date').size()

    print("   Date        Signals  Approved")
    print("   ----------  -------  --------")
    for date in sorted(daily_signals.index)[-10:]:  # Last 10 days
        signals = daily_signals.get(date, 0)
        approved = daily_approved.get(date, 0)
        print(f"   {date}  {signals:>7}  {approved:>8}")

    # 5. Signal Strength Analysis
    print("\n5. SIGNAL STRENGTH ANALYSIS:")
    approved_df = scan_df[scan_df['approved'] == 'YES']
    if not approved_df.empty:
        print(f"   Average Signal Strength (Approved): {approved_df['strength'].mean():.3f}")
        print(f"   Min Signal Strength: {approved_df['strength'].min():.3f}")
        print(f"   Max Signal Strength: {approved_df['strength'].max():.3f}")

    # 6. Summary Insights
    print("\n6. KEY INSIGHTS:")

    # Most active symbol
    if not symbol_df.empty:
        most_active = symbol_df.iloc[0]
        print(
            f"   - Most Active Symbol: {most_active['symbol']} ({most_active['total_signals']} signals)")

    # Optimal market heat
    if not heat_stats.empty:
        optimal_heat = heat_stats.idxmax()
        print(
            f"   - Optimal Market Heat: {optimal_heat:.2f} ({heat_stats[optimal_heat]:.1f}% approval)")

    # Trading frequency
    avg_daily_signals = len(scan_df) / len(daily_signals) if len(daily_signals) > 0 else 0
    print(f"   - Average Signals per Day: {avg_daily_signals:.1f}")

    # Save analysis results
    print("\n" + "=" * 80)

    # Save to CSV
    output_dir = Path(".cache/performance_reports")
    output_dir.mkdir(exist_ok=True)

    scan_df.to_csv(output_dir / "scan_analysis.csv", index=False)
    symbol_df.to_csv(output_dir / "symbol_performance.csv", index=False)

    print(f"\nResults saved to: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    analyze_scan_results()
