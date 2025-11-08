#!/usr/bin/env python3
"""
Polygon.io Data Collector for MAG 7 + Leveraged ETFs

Collects market data with rate limiting (5 calls/min for free tier)
and saves to unified cache format.
"""

import json
import time
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from polygon import RESTClient
from src.tools.cache.unified_cache import UnifiedCacheManager


class PolygonDataCollector:
    """Collect market data from Polygon.io with rate limiting."""

    def __init__(self, config_path: str = "config/config.json"):
        """Initialize with API configuration."""
        self.config_path = Path(config_path)
        self.load_config()

        # Initialize Polygon client
        self.client = RESTClient(self.polygon_key)

        # Initialize cache manager
        self.cache_manager = UnifiedCacheManager()

        # Rate limiting (free tier: 5 calls per minute)
        self.max_calls_per_minute = 5
        self.call_interval = 60.0 / self.max_calls_per_minute  # 12 seconds between calls
        self.last_call_time = 0

        # Symbol lists
        self.mag_7 = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA']

        # Leveraged ETFs
        self.leveraged_etfs = {
            # 2x/3x Bull ETFs for MAG 7 equivalents
            'TQQQ': 'ProShares UltraPro QQQ (3x NASDAQ)',
            'SQQQ': 'ProShares UltraPro Short QQQ (-3x NASDAQ)',
            'SOXL': 'Direxion Daily Semiconductor Bull 3x',
            'UVXY': 'ProShares Ultra VIX Short-Term Futures ETF',

            # Additional tech-focused leveraged ETFs
            'TECL': 'Direxion Daily Technology Bull 3x',
            'TECS': 'Direxion Daily Technology Bear 3x',
            'FNGU': 'MicroSectors FANG+ Index 3x Leveraged',
            'FNGD': 'MicroSectors FANG+ Index -3x Inverse',

            # Market-wide leveraged
            'SPXL': 'Direxion Daily S&P 500 Bull 3x',
            'SPXS': 'Direxion Daily S&P 500 Bear 3x',
            'UPRO': 'ProShares UltraPro S&P500 (3x)',
            'SPXU': 'ProShares UltraPro Short S&P500 (-3x)',

            # Additional volatility
            'VIXY': 'ProShares VIX Short-Term Futures ETF',
            'SVXY': 'ProShares Short VIX Short-Term Futures ETF'
        }

        # All symbols to collect
        self.all_symbols = self.mag_7 + list(self.leveraged_etfs.keys())

    def load_config(self):
        """Load API configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = json.load(f)

        self.polygon_key = config.get('POLYGON_IO')
        if not self.polygon_key:
            raise ValueError("POLYGON_IO key not found in config")

        print(f"Loaded Polygon.io API key: {self.polygon_key[:8]}...")

    def wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time

        if time_since_last_call < self.call_interval:
            wait_time = self.call_interval - time_since_last_call
            print(f"  Rate limiting: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)

        self.last_call_time = time.time()

    def fetch_daily_bars(self,
                         symbol: str,
                         start_date: str,
                         end_date: str) -> Optional[List[Dict]]:
        """Fetch daily OHLCV data from Polygon.io."""
        self.wait_for_rate_limit()

        try:
            print(f"  Fetching {symbol} from {start_date} to {end_date}...")

            # Get daily aggregates
            aggs = self.client.get_aggs(
                ticker=symbol,
                multiplier=1,
                timespan="day",
                from_=start_date,
                to=end_date,
                adjusted=True,
                sort="asc",
                limit=50000
            )

            # Handle response (can be list or object with results)
            if isinstance(aggs, list):
                bars_data = aggs
            elif hasattr(aggs, 'results') and aggs.results:
                bars_data = aggs.results
            else:
                print(f"  No data returned for {symbol}")
                return None

            if not bars_data:
                print(f"  No data bars for {symbol}")
                return None

            # Convert to our format
            bars = []
            for bar in bars_data:
                # Convert timestamp to date
                date_str = datetime.fromtimestamp(bar.timestamp / 1000).strftime('%Y-%m-%d')

                bars.append({
                    'date': date_str,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                    'vwap': float(getattr(bar, 'vwap', bar.close)),  # Volume weighted average price
                    'transactions': int(getattr(bar, 'transactions', 0))   # Number of transactions
                })

            print(f"  Successfully fetched {len(bars)} bars for {symbol}")
            return bars

        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            return None

    def save_to_cache(self,
                      symbol: str,
                      start_date: str,
                      end_date: str,
                      data: List[Dict]):
        """Save data to unified cache format."""
        cache_data = {
            'symbol': symbol,
            'start_date': start_date,
            'end_date': end_date,
            'source': 'polygon.io',
            'timestamp': datetime.now().isoformat(),
            'data_points': len(data),
            'data': data
        }

        # Create cache filename
        cache_dir = Path('.cache/market_data')
        cache_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{symbol}_{start_date}_{end_date}_polygon_consolidated.json"
        cache_file = cache_dir / filename

        # Save to file
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f, indent=2)

        print(f"  Saved {len(data)} data points to {cache_file}")

    def collect_symbol_data(self,
                            symbol: str,
                            start_date: str = "2024-01-01",
                            end_date: str = "2024-12-31") -> bool:
        """Collect data for a single symbol."""
        print(f"\nCollecting data for {symbol}...")

        # Check if we already have recent data
        cache_dir = Path('.cache/market_data')
        cache_pattern = f"{symbol}_{start_date}_{end_date}_polygon_consolidated.json"
        cache_file = cache_dir / cache_pattern

        if cache_file.exists():
            print(f"  Cache file already exists: {cache_file}")
            return True

        # Fetch data from Polygon.io
        data = self.fetch_daily_bars(symbol, start_date, end_date)

        if data:
            self.save_to_cache(symbol, start_date, end_date, data)
            return True
        else:
            print(f"  Failed to collect data for {symbol}")
            return False

    def collect_all_data(self,
                         start_date: str = "2024-01-01",
                         end_date: str = "2024-12-31"):
        """Collect data for all symbols."""
        print("Starting Polygon.io data collection...")
        print(f"Rate limit: {self.max_calls_per_minute} calls/minute (free tier)")
        print(f"Collecting data from {start_date} to {end_date}")
        print(f"Total symbols: {len(self.all_symbols)}")

        # Estimate time
        estimated_minutes = len(self.all_symbols) * self.call_interval / 60
        print(f"Estimated time: {estimated_minutes:.1f} minutes")
        print()

        success_count = 0
        failed_symbols = []

        start_time = time.time()

        # MAG 7 first
        print("Collecting MAG 7 data...")
        for symbol in self.mag_7:
            if self.collect_symbol_data(symbol, start_date, end_date):
                success_count += 1
            else:
                failed_symbols.append(symbol)

        print("\nCollecting Leveraged ETF data...")
        for symbol, description in self.leveraged_etfs.items():
            print(f"  {symbol}: {description}")
            if self.collect_symbol_data(symbol, start_date, end_date):
                success_count += 1
            else:
                failed_symbols.append(symbol)

        end_time = time.time()
        duration_minutes = (end_time - start_time) / 60

        # Summary
        print(f"\nData Collection Summary:")
        print(f"=" * 50)
        print(f"Total symbols: {len(self.all_symbols)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {len(failed_symbols)}")
        print(f"Duration: {duration_minutes:.1f} minutes")

        if failed_symbols:
            print(f"Failed symbols: {', '.join(failed_symbols)}")

        print(f"\nData saved to: .cache/market_data/")

        return success_count, failed_symbols

    def verify_data_quality(self):
        """Verify the quality of collected data."""
        print("\nVerifying data quality...")
        cache_dir = Path('.cache/market_data')

        verification_results = {}

        for symbol in self.all_symbols:
            cache_file = cache_dir / f"{symbol}_2024-01-01_2024-12-31_polygon_consolidated.json"

            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    data = json.load(f)

                bars = data.get('data', [])

                if bars:
                    # Basic quality checks
                    dates = [bar['date'] for bar in bars]
                    prices = [bar['close'] for bar in bars]
                    volumes = [bar['volume'] for bar in bars]

                    verification_results[symbol] = {
                        'data_points': len(bars),
                        'date_range': f"{min(dates)} to {max(dates)}",
                        'price_range': f"${min(prices):.2f} to ${max(prices):.2f}",
                        'avg_volume': sum(volumes) / len(volumes),
                        'has_gaps': len(set(dates)) != len(dates)  # Check for duplicates
                    }
                else:
                    verification_results[symbol] = {'error': 'No data bars found'}
            else:
                verification_results[symbol] = {'error': 'Cache file not found'}

        # Print verification report
        print("\nData Quality Report:")
        print("=" * 70)

        for symbol, result in verification_results.items():
            if 'error' in result:
                print(f"{symbol:6}: {result['error']}")
            else:
                print(f"{symbol:6}: {result['data_points']:3} bars, "
                      f"${result['price_range']:20}, "
                      f"avg vol: {result['avg_volume']:,.0f}")

        return verification_results


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Collect market data from Polygon.io')
    parser.add_argument('--start', default='2024-01-01', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', default='2024-12-31', help='End date (YYYY-MM-DD)')
    parser.add_argument('--verify', action='store_true',
                        help='Verify data quality after collection')
    parser.add_argument('--symbols', help='Comma-separated list of specific symbols to collect')

    args = parser.parse_args()

    # Create collector
    collector = PolygonDataCollector()

    if args.symbols:
        # Collect specific symbols
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
        print(f"Collecting data for specific symbols: {symbols}")

        success_count = 0
        for symbol in symbols:
            if collector.collect_symbol_data(symbol, args.start, args.end):
                success_count += 1

        print(f"\nCollected {success_count}/{len(symbols)} symbols successfully")
    else:
        # Collect all symbols
        success_count, failed_symbols = collector.collect_all_data(args.start, args.end)

    if args.verify:
        collector.verify_data_quality()


if __name__ == "__main__":
    main()
