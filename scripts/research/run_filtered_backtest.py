"""
Run Filtered Backtest (#264)

Demonstrates the practical trading filters applied to backtest results.
Compares filtered vs unfiltered performance to measure filter effectiveness.

Usage:
    python scripts/research/run_filtered_backtest.py --symbol AAPL --year 2024
    python scripts/research/run_filtered_backtest.py --symbol SPY --filters volume,vix
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd


def create_sample_data(days: int = 252) -> pd.DataFrame:
    """Create sample OHLCV data for testing filters."""
    import numpy as np

    np.random.seed(42)

    dates = pd.date_range(end="2024-12-31", periods=days, freq="B")

    # Simulate price series with some volatility
    returns = np.random.normal(0.0005, 0.015, days)
    prices = 100 * np.exp(np.cumsum(returns))

    # Simulate volume with some low-volume days
    base_volume = 1_000_000
    volume = base_volume * (0.5 + np.random.random(days))
    # Add some extremely low volume days
    low_vol_days = np.random.choice(days, size=20, replace=False)
    volume[low_vol_days] *= 0.2

    # Add some gap days
    gap_days = np.random.choice(days, size=10, replace=False)
    for day in gap_days:
        if day > 0:
            prices[day] *= 1 + np.random.choice([-1, 1]) * np.random.uniform(0.02, 0.05)

    df = pd.DataFrame(
        {
            "open": prices * (1 + np.random.uniform(-0.005, 0.005, days)),
            "high": prices * (1 + np.random.uniform(0, 0.02, days)),
            "low": prices * (1 - np.random.uniform(0, 0.02, days)),
            "close": prices,
            "volume": volume.astype(int),
        },
        index=dates,
    )

    return df


def _print_header():
    """Print report header."""
    print("=" * 70)
    print("FILTERED BACKTEST COMPARISON")
    print("=" * 70)
    print()


def _print_filter_stats(filters, skipped_days, size_adjustments, total_days):
    """Print filter statistics and samples."""
    stats = filters.get_stats()
    print("FILTER TRIGGER COUNTS")
    print("-" * 40)
    for name, stat_data in stats.items():
        print(f"  {name}: {stat_data['triggers']} triggers, {stat_data['skip_count']} skips")
    print()

    if skipped_days:
        print("SAMPLE SKIPPED DAYS (first 10)")
        print("-" * 40)
        for date_str, reason in skipped_days[:10]:
            print(f"  {date_str}: {reason}")
        print()

    if size_adjustments:
        print("SAMPLE SIZE ADJUSTMENTS (first 10)")
        print("-" * 40)
        for date_str, mult, reason in size_adjustments[:10]:
            print(f"  {date_str}: {mult:.0%} - {reason}")
        print()


def _print_summary(skipped_days, total_days):
    """Print summary with skip rate assessment."""
    skip_rate = len(skipped_days) / total_days * 100
    print("SUMMARY")
    print("-" * 40)
    print(f"Skip rate: {skip_rate:.1f}%")
    print(f"Tradeable days: {100 - skip_rate:.1f}%")
    print()

    if skip_rate > 30:
        print("Warning: High skip rate. Consider relaxing filter thresholds.")
    elif skip_rate < 5:
        print("Low skip rate. Filters may be too lenient.")
    else:
        print("Reasonable skip rate. Filters are balanced.")


def run_filter_comparison():
    """Compare filtered vs unfiltered trading."""
    import numpy as np

    from src.backtesting.trading_filters import create_standard_filters

    _print_header()

    # Create sample data
    data = create_sample_data(252)
    print(f"Sample data: {len(data)} trading days")
    print(f"Date range: {data.index[0].date()} to {data.index[-1].date()}")
    print()

    # Create filter manager
    filters = create_standard_filters()
    print("Active Filters:", ", ".join(f.name for f in filters.filters))
    print()

    # Simulate trading
    skipped_days = []
    size_adjustments = []

    np.random.seed(123)
    vix_series = 15 + 10 * np.random.random(len(data))
    vix_series[50:60] = 35

    for i in range(20, len(data)):
        date_str = data.index[i].strftime("%Y-%m-%d")
        result = filters.apply_all("AAPL", date_str, data.iloc[: i + 1], {"vix": vix_series[i]})

        if result.skip:
            skipped_days.append((date_str, result.reason))
        elif result.size_multiplier < 1.0:
            size_adjustments.append((date_str, result.size_multiplier, result.reason))

    total_days = len(data) - 20
    print("RESULTS")
    print("-" * 40)
    print(f"Total trading days: {total_days}")
    print(f"Skipped days: {len(skipped_days)}")
    print(f"Days with size adjustment: {len(size_adjustments)}")
    print()

    _print_filter_stats(filters, skipped_days, size_adjustments, total_days)
    _print_summary(skipped_days, total_days)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run filtered backtest comparison")
    parser.add_argument("--symbol", default="AAPL", help="Symbol to test")
    parser.add_argument("--year", type=int, default=2024, help="Year to test")
    parser.parse_args()  # Parse but don't store (using sample data for demo)

    run_filter_comparison()
    return 0


if __name__ == "__main__":
    sys.exit(main())
