#!/usr/bin/env python3
"""
News Data Collector for MAG7 stocks using Google Search API.

This module handles systematic collection of financial news data
with quota management and caching for sentiment analysis.
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

from src.tools.data_sources.news.aggregators.hybrid_historical_news_tool import hybrid_historical_news_tool
from config.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsDataCollector:
    """
    Systematic news data collector for MAG7 stocks.

    Features:
    - Google Search API quota management (90/100 per day)
    - 15-minute intervals between searches
    - Progress tracking and resumable collection
    - Compatible with existing news cache structure
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

    SEARCH_PATTERNS = [
        '{ticker} stock crash April 2025',
        '{ticker} market decline Q2 2025',
        '{ticker} earnings volatility 2025'
    ]

    def __init__(self):
        """Initialize the news data collector."""
        # Validate Google Search API availability
        config_loader = ConfigLoader()
        api_key = config_loader.get("GOOGLE_SEARCH_API_KEY")
        engine_id = config_loader.get("GOOGLE_SEARCH_ENGINE_ID")

        if not api_key or not engine_id:
            raise ValueError("Google Search API credentials not found in config.json")

        # Setup progress tracking
        self.status_dir = Path('.cache/mag7_collection')
        self.status_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.status_dir / 'news_data_status.json'

        # Quota and rate limiting
        self.daily_quota = 90  # Leave 10 searches for manual use
        self.rate_limit_delay = 900  # 15 minutes between searches

        logger.info("News data collector initialized")
        logger.info(f"Daily quota: {self.daily_quota}/100 searches")
        logger.info(f"Rate limit: {self.rate_limit_delay/60} minutes between searches")

    def load_status(self) -> Dict:
        """Load collection status from disk."""
        if not self.status_file.exists():
            return {
                'completed_searches': [],
                'failed_searches': [],
                'daily_usage': {},  # Track usage by date
                'last_search_time': 0,
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

    def check_daily_quota(self, status: Dict) -> bool:
        """
        Check if we have quota remaining for today.

        Args:
            status: Current status dict

        Returns:
            True if quota available, False if exhausted
        """
        today = datetime.now().strftime('%Y-%m-%d')
        today_usage = status['daily_usage'].get(today, 0)

        if today_usage >= self.daily_quota:
            logger.warning(f"Daily quota exhausted: {today_usage}/{self.daily_quota}")
            return False

        remaining = self.daily_quota - today_usage
        logger.info(f"Daily quota remaining: {remaining}/{self.daily_quota}")
        return True

    def collect_ticker_news(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        status: Dict
    ) -> bool:
        """
        Collect news for a single ticker and date range.

        Args:
            ticker: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            status: Current status dict

        Returns:
            True if successful, False if failed
        """
        # Check daily quota first
        if not self.check_daily_quota(status):
            logger.warning("Daily quota exhausted - stopping collection")
            return False

        search_key = f"{ticker}_{start_date}_{end_date}"

        # Check if already completed
        if search_key in status['completed_searches']:
            logger.info(f"Skipping {search_key} - already completed")
            return True

        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - status['last_search_time']

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.info(f"Rate limiting: sleeping for {sleep_time/60:.1f} minutes")
            time.sleep(sleep_time)

        # Update status
        status['current_ticker'] = ticker
        status['last_search_time'] = time.time()
        today = datetime.now().strftime('%Y-%m-%d')

        try:
            logger.info(f"Collecting news for {ticker} from {start_date} to {end_date}")

            # Use existing hybrid news tool
            search_query = f"{ticker} stock market crash Q2 2025"

            news_df = hybrid_historical_news_tool(
                query=search_query,
                start_date=start_date,
                end_date=end_date,
                max_results=20
            )

            if not news_df.empty:
                logger.info(f"✓ Successfully collected {len(news_df)} articles for {ticker}")
                status['completed_searches'].append(search_key)

                # Update daily usage
                status['daily_usage'][today] = status['daily_usage'].get(today, 0) + 1

                return True
            else:
                logger.warning(f"⚠ No news found for {ticker}")
                status['failed_searches'].append(search_key)
                # Still count as quota usage
                status['daily_usage'][today] = status['daily_usage'].get(today, 0) + 1
                return False

        except Exception as e:
            logger.error(f"✗ Failed to collect news for {ticker}: {e}")
            status['failed_searches'].append(search_key)
            # Still count as quota usage
            status['daily_usage'][today] = status['daily_usage'].get(today, 0) + 1
            return False

        finally:
            # Always save status after each attempt
            status['total_progress'] += 1
            self.save_status(status)

    def collect_week_news(self, start_date: str, end_date: str) -> Dict:
        """
        Collect one week of news for all MAG7 tickers.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Collection summary dict
        """
        status = self.load_status()

        if not status['start_time']:
            status['start_time'] = datetime.now().isoformat()

        logger.info(f"Starting MAG7 news collection for {start_date} to {end_date}")
        logger.info(f"Tickers: {', '.join(self.MAG7_TICKERS)}")
        logger.info(f"Rate limit: {self.rate_limit_delay/60} minutes between searches")

        successful_collections = 0
        failed_collections = 0
        quota_exhausted = False

        for ticker in self.MAG7_TICKERS:
            # Check quota before each ticker
            if not self.check_daily_quota(status):
                quota_exhausted = True
                logger.warning("Daily quota exhausted - stopping collection")
                break

            success = self.collect_ticker_news(ticker, start_date, end_date, status)

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

        today = datetime.now().strftime('%Y-%m-%d')
        today_usage = status['daily_usage'].get(today, 0)

        summary = {
            'period': f"{start_date} to {end_date}",
            'successful_collections': successful_collections,
            'failed_collections': failed_collections,
            'total_planned': len(self.MAG7_TICKERS),
            'success_rate': f"{(successful_collections/(successful_collections+failed_collections)*100):.1f}%" if (successful_collections + failed_collections) > 0 else "0%",
            'quota_usage': f"{today_usage}/{self.daily_quota}",
            'quota_exhausted': quota_exhausted,
            'duration': str(duration),
            'completed_at': end_time.isoformat()
        }

        logger.info("=" * 60)
        logger.info("NEWS COLLECTION SUMMARY")
        logger.info("=" * 60)
        for key, value in summary.items():
            logger.info(f"{key}: {value}")
        logger.info("=" * 60)

        if quota_exhausted:
            logger.info("⚠️  QUOTA EXHAUSTED - Resume tomorrow or use fewer tickers")

        return summary

    def collect_test_week_news(self) -> Dict:
        """
        Collect test news for peak volatility week (April 9-16, 2025).

        Returns:
            Collection summary
        """
        # Peak volatility period from our analysis
        start_date = "2025-04-09"
        end_date = "2025-04-16"

        logger.info("📰 COLLECTING TEST WEEK NEWS")
        logger.info("Period: Peak MAG7 volatility (April 9-16, 2025)")
        logger.info("Expected: Market crash and volatility news")

        return self.collect_week_news(start_date, end_date)

    def get_collection_status(self) -> Dict:
        """Get current collection status and progress."""
        status = self.load_status()

        today = datetime.now().strftime('%Y-%m-%d')
        today_usage = status['daily_usage'].get(today, 0)

        return {
            'total_completed': len(status['completed_searches']),
            'total_failed': len(status['failed_searches']),
            'today_quota_usage': f"{today_usage}/{self.daily_quota}",
            'last_search_time': status['last_search_time'],
            'current_ticker': status['current_ticker'],
            'start_time': status['start_time'],
            'daily_usage_history': status['daily_usage']
        }

    def validate_news_cache(self) -> Dict:
        """
        Validate that collected news is properly cached and accessible.

        Returns:
            Validation summary
        """
        logger.info("Validating news cache structure...")

        # Check Google Search cache
        google_cache_dir = Path('.cache/news/google_search')
        cache_files = list(google_cache_dir.glob('*.json')) if google_cache_dir.exists() else []

        validation = {
            'google_cache_dir_exists': google_cache_dir.exists(),
            'total_cache_files': len(cache_files),
            'recent_cache_files': [f.name for f in sorted(cache_files, key=lambda x: x.stat().st_mtime)[-3:]]
        }

        logger.info("News Cache Validation Results:")
        for key, value in validation.items():
            logger.info(f"  {key}: {value}")

        return validation


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description='MAG7 News Data Collector')
    parser.add_argument('--test-week', action='store_true',
                        help='Collect test week news (April 9-16, 2025)')
    parser.add_argument('--status', action='store_true',
                        help='Show collection status')
    parser.add_argument('--validate', action='store_true',
                        help='Validate news cache structure')
    parser.add_argument('--start-date', type=str,
                        help='Custom start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                        help='Custom end date (YYYY-MM-DD)')

    args = parser.parse_args()

    try:
        collector = NewsDataCollector()

        if args.status:
            status = collector.get_collection_status()
            print("\n📊 NEWS COLLECTION STATUS")
            print("=" * 50)
            for key, value in status.items():
                print(f"{key}: {value}")

        elif args.validate:
            validation = collector.validate_news_cache()
            print("\n✅ NEWS CACHE VALIDATION")
            print("=" * 50)
            for key, value in validation.items():
                print(f"{key}: {value}")

        elif args.test_week:
            summary = collector.collect_test_week_news()
            print("\n📰 TEST WEEK NEWS COLLECTION COMPLETE")

        elif args.start_date and args.end_date:
            summary = collector.collect_week_news(args.start_date, args.end_date)
            print("\n📈 CUSTOM PERIOD NEWS COLLECTION COMPLETE")

        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"News collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
