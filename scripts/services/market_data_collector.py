#!/usr/bin/env python3
"""
Market Data Collector for MAG7 stocks using Polygon.io API.

This module handles systematic collection of historical market data
with rate limiting and caching for the RH2MAS backtesting system.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import json
from datetime import datetime
from typing import Dict
from pathlib import Path
import logging

from src.tools.data_sources.market.polygon_historical_tool import PolygonHistoricalData
from config.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketDataCollector:
    """
    Systematic market data collector for MAG7 stocks.

    Features:
    - Rate-limited data collection (60-second intervals)
    - Progress tracking and resumable collection
    - JSON-based status tracking
    - Compatible with existing cache structure
    """

    MAG7_TICKERS = [
        'AAPL',  # Apple Inc
        'MSFT',  # Microsoft Corp
        'GOOGL',  # Alphabet Inc
        'AMZN',  # Amazon.com Inc
        'NVDA',  # NVIDIA Corp
        'TSLA',  # Tesla Inc
        'META'   # Meta Platforms
    ]

    def __init__(self):
        """Initialize the market data collector."""
        # Load API key
        config_loader = ConfigLoader()
        api_key = config_loader.get("POLYGON_IO")
        if not api_key:
            raise ValueError("POLYGON_IO API key not found in config.json")

        self.polygon_client = PolygonHistoricalData(api_key=api_key)

        # Setup progress tracking
        self.status_dir = Path('.cache/mag7_collection')
        self.status_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.status_dir / 'market_data_status.json'

        # Rate limiting - be conservative with free tier
        self.rate_limit_delay = 65  # 65 seconds between requests

        logger.info("Market data collector initialized")

    def load_status(self) -> Dict:
        """Load collection status from disk."""
        if not self.status_file.exists():
            return {
                'completed_requests': [],
                'failed_requests': [],
                'last_request_time': 0,
                'total_progress': 0,
                'start_time': None,
                'current_ticker': None
            }

        try:
            with open(self.status_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load status file: {e}")
            return self.load_status()  # Return default

    def save_status(self, status: Dict):
        """Save collection status to disk."""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save status: {e}")

    def collect_ticker_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        status: Dict
    ) -> bool:
        """
        Collect data for a single ticker and date range.

        Args:
            ticker: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)  
            status: Current status dict

        Returns:
            True if successful, False if failed
        """
        request_key = f"{ticker}_{start_date}_{end_date}"

        # Check if already completed
        if request_key in status['completed_requests']:
            logger.info(f"Skipping {request_key} - already completed")
            return True

        # Check if previously failed (skip retries for now)
        if request_key in status['failed_requests']:
            logger.info(f"Skipping {request_key} - previously failed")
            return False

        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - status['last_request_time']

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.info(f"Rate limiting: sleeping for {sleep_time:.1f}s")
            time.sleep(sleep_time)

        # Update status
        status['current_ticker'] = ticker
        status['last_request_time'] = time.time()
        self.save_status(status)

        try:
            logger.info(f"Collecting {ticker} data from {start_date} to {end_date}")

            # Fetch historical prices
            prices_df = self.polygon_client.fetch_historical_prices(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                use_cache=True  # Let caching system handle duplicates
            )

            if not prices_df.empty:
                logger.info(f"✓ Successfully collected {len(prices_df)} days for {ticker}")
                status['completed_requests'].append(request_key)
                return True
            else:
                logger.warning(f"⚠ No data returned for {ticker}")
                status['failed_requests'].append(request_key)
                return False

        except Exception as e:
            logger.error(f"✗ Failed to collect {ticker} data: {e}")
            status['failed_requests'].append(request_key)
            return False

        finally:
            # Always save status after each attempt
            status['total_progress'] += 1
            self.save_status(status)

    def collect_week_data(self, start_date: str, end_date: str) -> Dict:
        """
        Collect one week of data for all MAG7 tickers.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Collection summary dict
        """
        status = self.load_status()

        if not status['start_time']:
            status['start_time'] = datetime.now().isoformat()

        logger.info(f"Starting MAG7 data collection for {start_date} to {end_date}")
        logger.info(f"Tickers: {', '.join(self.MAG7_TICKERS)}")
        logger.info(f"Rate limit: {self.rate_limit_delay} seconds between requests")

        successful_collections = 0
        failed_collections = 0

        for ticker in self.MAG7_TICKERS:
            success = self.collect_ticker_data(ticker, start_date, end_date, status)

            if success:
                successful_collections += 1
            else:
                failed_collections += 1

            # Progress update
            completed = successful_collections + failed_collections
            total = len(self.MAG7_TICKERS)
            progress_pct = (completed / total) * 100

            logger.info(f"Progress: {completed}/{total} ({progress_pct:.1f}%) - "
                        f"Success: {successful_collections}, Failed: {failed_collections}")

        # Final summary
        end_time = datetime.now()
        start_time = datetime.fromisoformat(status['start_time'])
        duration = end_time - start_time

        summary = {
            'period': f"{start_date} to {end_date}",
            'successful_collections': successful_collections,
            'failed_collections': failed_collections,
            'total_requests': len(self.MAG7_TICKERS),
            'success_rate': f"{(successful_collections/len(self.MAG7_TICKERS)*100):.1f}%",
            'duration': str(duration),
            'completed_at': end_time.isoformat()
        }

        logger.info("=" * 60)
        logger.info("COLLECTION SUMMARY")
        logger.info("=" * 60)
        for key, value in summary.items():
            logger.info(f"{key}: {value}")
        logger.info("=" * 60)

        return summary

    def collect_test_week(self) -> Dict:
        """
        Collect test data for peak volatility week (April 9-16, 2025).

        Returns:
            Collection summary
        """
        # Peak volatility period from our analysis
        start_date = "2025-04-09"
        end_date = "2025-04-16"

        logger.info("🎯 COLLECTING TEST WEEK DATA")
        logger.info("Period: Peak MAG7 volatility (April 9-16, 2025)")
        logger.info("Expected: AAPL (-33.4%), META (-34.2%) crash data")

        return self.collect_week_data(start_date, end_date)

    def get_collection_status(self) -> Dict:
        """Get current collection status and progress."""
        status = self.load_status()

        return {
            'total_completed': len(status['completed_requests']),
            'total_failed': len(status['failed_requests']),
            'last_request_time': status['last_request_time'],
            'current_ticker': status['current_ticker'],
            'start_time': status['start_time'],
            'cache_directory': str(self.polygon_client.cache_dir),
        }

    def validate_cache_structure(self) -> Dict:
        """
        Validate that collected data is properly cached and accessible.

        Returns:
            Validation summary
        """
        logger.info("Validating cache structure...")

        cache_dir = self.polygon_client.cache_dir
        prices_dir = cache_dir / 'prices'

        cache_files = list(prices_dir.glob('*.json')) if prices_dir.exists() else []

        validation = {
            'cache_directory_exists': cache_dir.exists(),
            'prices_directory_exists': prices_dir.exists(),
            'total_cache_files': len(cache_files),
            'cache_files': [f.name for f in cache_files[-5:]]  # Show last 5 files
        }

        logger.info("Cache Validation Results:")
        for key, value in validation.items():
            logger.info(f"  {key}: {value}")

        return validation


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description='MAG7 Market Data Collector')
    parser.add_argument('--test-week', action='store_true',
                        help='Collect test week data (April 9-16, 2025)')
    parser.add_argument('--status', action='store_true',
                        help='Show collection status')
    parser.add_argument('--validate', action='store_true',
                        help='Validate cache structure')
    parser.add_argument('--start-date', type=str,
                        help='Custom start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                        help='Custom end date (YYYY-MM-DD)')

    args = parser.parse_args()

    try:
        collector = MarketDataCollector()

        if args.status:
            status = collector.get_collection_status()
            print("\n📊 COLLECTION STATUS")
            print("=" * 50)
            for key, value in status.items():
                print(f"{key}: {value}")

        elif args.validate:
            validation = collector.validate_cache_structure()
            print("\n✅ CACHE VALIDATION")
            print("=" * 50)
            for key, value in validation.items():
                print(f"{key}: {value}")

        elif args.test_week:
            summary = collector.collect_test_week()
            print("\n🎯 TEST WEEK COLLECTION COMPLETE")

        elif args.start_date and args.end_date:
            summary = collector.collect_week_data(args.start_date, args.end_date)
            print("\n📈 CUSTOM PERIOD COLLECTION COMPLETE")

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"Collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
