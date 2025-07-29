#!/usr/bin/env python3
"""
Build FMP Cache - Collect stock data during low-usage periods

Slowly build up cached stock data from FMP during quiet periods to avoid 
rate limits during active backtesting. Focus on key periods and symbols.
"""

import sys
import time
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.data_sources.market.fmp_tool import FMPTool


def get_priority_symbols() -> List[str]:
    """Get priority symbols for caching based on validation needs."""
    return [
        # Core validation symbols
        'SPY', 'AAPL', 'TSLA', 'NVDA',
        # MAG7 for comprehensive testing
        'MSFT', 'GOOGL', 'AMZN', 'META',
        # Market sectors for diversity
        'QQQ', 'XLF', 'XLK', 'VXX'
    ]


def get_priority_periods() -> List[Dict[str, str]]:
    """Get priority date ranges for caching."""
    return [
        # 2022 bear market (high validation value)
        {'name': '2022_bear', 'start': '2022-01-01', 'end': '2022-12-31'},
        # 2023 bull market (missing data)
        {'name': '2023_bull', 'start': '2023-01-01', 'end': '2023-12-31'},
        # 2020 COVID crash (stress testing)
        {'name': '2020_covid', 'start': '2020-02-15', 'end': '2020-05-15'},
        # Recent periods (current analysis)
        {'name': '2024_recent', 'start': '2024-01-01', 'end': '2024-12-31'},
        # Q1 2025 (latest data)
        {'name': '2025_q1', 'start': '2025-01-01', 'end': '2025-03-31'}
    ]


def check_existing_cache(symbol: str, start_date: str, end_date: str) -> bool:
    """Check if we already have cached data for this period."""
    cache_dir = Path(".cache/market_data")

    if not cache_dir.exists():
        return False

    # Look for any CSV files that might contain this data
    cache_files = list(cache_dir.glob(f"*{symbol}*.csv"))

    for cache_file in cache_files:
        try:
            df = pd.read_csv(cache_file)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)

                # Check if we have data covering this period
                if df['date'].min() <= start_dt and df['date'].max() >= end_dt:
                    return True
        except:
            continue

    return False


def safe_fetch_with_retry(fmp_tool: FMPTool, symbol: str, start_date: str, end_date: str, max_retries: int = 3) -> pd.DataFrame:
    """Safely fetch data with retry logic and rate limit handling."""

    for attempt in range(max_retries):
        try:
            print(f"  Attempt {attempt + 1}: Fetching {symbol} from {start_date} to {end_date}")

            data = fmp_tool.fetch_stock_data(symbol, start_date, end_date)

            if data is not None and not data.empty:
                print(f"  ✅ Success: {len(data)} records for {symbol}")
                return data
            else:
                print(f"  ⚠️  Empty data returned for {symbol}")

        except Exception as e:
            error_msg = str(e)
            print(f"  ❌ Error: {error_msg}")

            if "429" in error_msg or "Too Many Requests" in error_msg:
                print(f"  🛑 Rate limit hit! Waiting 60 seconds...")
                time.sleep(60)
                continue
            elif "403" in error_msg or "Forbidden" in error_msg:
                print(f"  🚫 API access denied. Skipping {symbol}")
                break
            else:
                print(f"  ⏳ Waiting 5 seconds before retry...")
                time.sleep(5)

    print(f"  ❌ Failed to fetch {symbol} after {max_retries} attempts")
    return pd.DataFrame()


def save_to_cache(data: pd.DataFrame, symbol: str, period_name: str):
    """Save data to cache directory."""
    cache_dir = Path(".cache/market_data")
    cache_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{symbol}_{period_name}_{timestamp}.csv"
    filepath = cache_dir / filename

    data.to_csv(filepath, index=False)
    print(f"  💾 Saved to: {filepath}")


def main():
    """Main cache building function."""
    print("=== FMP Cache Builder ===")
    print("Building stock data cache during low-usage period\n")

    # Initialize FMP tool
    try:
        fmp_tool = FMPTool()
        print("✅ FMP API initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize FMP API: {e}")
        return

    symbols = get_priority_symbols()
    periods = get_priority_periods()

    total_tasks = len(symbols) * len(periods)
    completed = 0
    successful = 0

    print(
        f"📋 Planning to cache {len(symbols)} symbols × {len(periods)} periods = {total_tasks} tasks")
    print(f"⏰ Estimated time: {total_tasks * 10 / 60:.1f} minutes (with rate limiting)\n")

    # Track progress
    start_time = datetime.now()

    for period in periods:
        print(f"\n=== Period: {period['name']} ({period['start']} to {period['end']}) ===")

        for symbol in symbols:
            completed += 1
            print(f"\n[{completed}/{total_tasks}] Processing {symbol} for {period['name']}")

            # Check if we already have this data
            if check_existing_cache(symbol, period['start'], period['end']):
                print(f"  ✅ Already cached - skipping")
                successful += 1
                continue

            # Fetch the data
            data = safe_fetch_with_retry(fmp_tool, symbol, period['start'], period['end'])

            if not data.empty:
                save_to_cache(data, symbol, period['name'])
                successful += 1
                print(f"  ✅ Cached successfully")
            else:
                print(f"  ❌ Failed to cache")

            # Rate limiting: wait between requests
            print(f"  ⏳ Waiting 10 seconds before next request...")
            time.sleep(10)

    # Final summary
    elapsed = datetime.now() - start_time
    print(f"\n=== Cache Building Complete ===")
    print(f"📊 Results: {successful}/{total_tasks} successful ({successful/total_tasks*100:.1f}%)")
    print(f"⏰ Time elapsed: {elapsed.total_seconds()/60:.1f} minutes")
    print(f"💾 Cache directory: .cache/market_data/")

    if successful > 0:
        print(f"✅ Successfully cached data for future backtests!")
    else:
        print(f"❌ No data was cached - check API limits and keys")


if __name__ == "__main__":
    main()
