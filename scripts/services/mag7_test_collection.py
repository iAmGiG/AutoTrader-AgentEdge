#!/usr/bin/env python3
"""
MAG7 Test Week Data Collection Orchestrator.

This script coordinates both market data and news collection
for a test week to validate the caching system works properly
before full-scale data collection.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
import json
from datetime import datetime
from pathlib import Path
import logging

from market_data_collector import MarketDataCollector
from news_data_collector import NewsDataCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MAG7TestCollection:
    """
    Orchestrates test data collection for validation.

    Collects one week of data (April 9-16, 2025) to validate:
    - Polygon.io market data caching works properly
    - Google Search news caching works properly
    - Existing tools can read from the new cache structure
    - Rate limiting is functioning correctly
    """

    def __init__(self):
        """Initialize the test collection orchestrator."""
        self.market_collector = MarketDataCollector()
        self.news_collector = NewsDataCollector()

        self.test_start_date = "2025-04-09"  # Peak volatility start
        self.test_end_date = "2025-04-16"    # One week of data

        # Results tracking
        self.results_dir = Path('.cache/mag7_collection')
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.results_file = self.results_dir / 'test_collection_results.json'

        logger.info("MAG7 Test Collection initialized")
        logger.info(f"Test period: {self.test_start_date} to {self.test_end_date}")

    def run_market_data_collection(self) -> dict:
        """
        Run market data collection for test week.

        Returns:
            Collection summary
        """
        logger.info("🏛️ STARTING MARKET DATA COLLECTION")
        logger.info("=" * 60)

        start_time = datetime.now()

        try:
            summary = self.market_collector.collect_week_data(
                self.test_start_date,
                self.test_end_date
            )

            summary['collection_type'] = 'market_data'
            summary['start_time'] = start_time.isoformat()
            summary['success'] = True

            return summary

        except Exception as e:
            logger.error(f"Market data collection failed: {e}")
            return {
                'collection_type': 'market_data',
                'start_time': start_time.isoformat(),
                'success': False,
                'error': str(e)
            }

    def run_news_collection(self) -> dict:
        """
        Run news collection for test week.

        Returns:
            Collection summary
        """
        logger.info("📰 STARTING NEWS DATA COLLECTION")
        logger.info("=" * 60)

        start_time = datetime.now()

        try:
            summary = self.news_collector.collect_week_news(
                self.test_start_date,
                self.test_end_date
            )

            summary['collection_type'] = 'news_data'
            summary['start_time'] = start_time.isoformat()
            summary['success'] = True

            return summary

        except Exception as e:
            logger.error(f"News collection failed: {e}")
            return {
                'collection_type': 'news_data',
                'start_time': start_time.isoformat(),
                'success': False,
                'error': str(e)
            }

    def validate_cache_integration(self) -> dict:
        """
        Validate that cached data can be read by existing tools.

        Returns:
            Validation results
        """
        logger.info("✅ VALIDATING CACHE INTEGRATION")
        logger.info("=" * 60)

        validation_results = {
            'market_data_validation': {},
            'news_data_validation': {},
            'integration_tests': {}
        }

        # Test 1: Market data cache validation
        try:
            market_validation = self.market_collector.validate_cache_structure()
            validation_results['market_data_validation'] = market_validation
            logger.info("✓ Market data cache validation completed")
        except Exception as e:
            logger.error(f"Market data cache validation failed: {e}")
            validation_results['market_data_validation'] = {'error': str(e)}

        # Test 2: News data cache validation
        try:
            news_validation = self.news_collector.validate_news_cache()
            validation_results['news_data_validation'] = news_validation
            logger.info("✓ News data cache validation completed")
        except Exception as e:
            logger.error(f"News data cache validation failed: {e}")
            validation_results['news_data_validation'] = {'error': str(e)}

        # Test 3: Integration with existing tools
        try:
            integration_tests = self._test_tool_integration()
            validation_results['integration_tests'] = integration_tests
            logger.info("✓ Tool integration tests completed")
        except Exception as e:
            logger.error(f"Tool integration tests failed: {e}")
            validation_results['integration_tests'] = {'error': str(e)}

        return validation_results

    def _test_tool_integration(self) -> dict:
        """
        Test that existing tools can read the cached data.

        Returns:
            Integration test results
        """
        logger.info("Testing integration with existing tools...")

        integration_results = {
            'polygon_tool_test': False,
            'news_tool_test': False,
            'errors': []
        }

        # Test 1: Polygon tool can read cached data
        try:
            from src.tools.tools import fetch_polygon_historical_data

            result = fetch_polygon_historical_data(
                ticker="AAPL",
                start_date=self.test_start_date,
                end_date=self.test_end_date,
                data_type="prices"
            )

            if result and 'prices' in result and len(result['prices']) > 0:
                integration_results['polygon_tool_test'] = True
                logger.info("✓ Polygon tool can read cached data")
            else:
                integration_results['errors'].append("Polygon tool returned empty data")
                logger.warning("⚠ Polygon tool returned empty data")

        except Exception as e:
            integration_results['errors'].append(f"Polygon tool test failed: {e}")
            logger.error(f"✗ Polygon tool test failed: {e}")

        # Test 2: News tool can read cached data
        try:
            news_result = self.news_collector.hybrid_historical_news_tool(
                query="AAPL market crash",
                start_date=self.test_start_date,
                end_date=self.test_end_date,
                max_results=5
            )

            if not news_result.empty:
                integration_results['news_tool_test'] = True
                logger.info("✓ News tool can read cached data")
            else:
                integration_results['errors'].append("News tool returned empty data")
                logger.warning("⚠ News tool returned empty data")

        except Exception as e:
            integration_results['errors'].append(f"News tool test failed: {e}")
            logger.error(f"✗ News tool test failed: {e}")

        return integration_results

    def run_full_test_collection(self) -> dict:
        """
        Run complete test collection with both market and news data.

        Returns:
            Complete test results
        """
        logger.info("🚀 STARTING COMPLETE MAG7 TEST COLLECTION")
        logger.info("=" * 80)
        logger.info(f"Test Period: {self.test_start_date} to {self.test_end_date}")
        logger.info(f"Expected Duration: ~10-15 minutes (7 tickers × 65s intervals)")
        logger.info(f"News Collection: Limited by daily quota (90/100 searches)")
        logger.info("=" * 80)

        overall_start = datetime.now()
        results = {
            'test_period': f"{self.test_start_date} to {self.test_end_date}",
            'start_time': overall_start.isoformat(),
            'collections': {},
            'validation': {},
            'overall_success': False
        }

        # Step 1: Market Data Collection
        market_results = self.run_market_data_collection()
        results['collections']['market_data'] = market_results

        # Step 2: News Data Collection (if market data succeeded)
        if market_results['success']:
            logger.info("\n⏳ WAITING 2 MINUTES BEFORE NEWS COLLECTION...")
            logger.info("(Allowing market data collection to complete)")
            time.sleep(120)  # 2-minute buffer

            news_results = self.run_news_collection()
            results['collections']['news_data'] = news_results
        else:
            logger.warning("Skipping news collection due to market data failure")
            results['collections']['news_data'] = {
                'success': False,
                'skipped': True,
                'reason': 'Market data collection failed'
            }

        # Step 3: Validation
        logger.info("\n⏳ WAITING 1 MINUTE BEFORE VALIDATION...")
        time.sleep(60)  # 1-minute buffer

        validation_results = self.validate_cache_integration()
        results['validation'] = validation_results

        # Final summary
        overall_end = datetime.now()
        overall_duration = overall_end - overall_start

        results['end_time'] = overall_end.isoformat()
        results['total_duration'] = str(overall_duration)

        # Determine overall success
        market_success = market_results.get('success', False)
        news_success = results['collections']['news_data'].get('success', False)
        validation_success = (
            validation_results.get('market_data_validation', {}).get('cache_directory_exists', False) and
            validation_results.get('integration_tests', {}).get('polygon_tool_test', False)
        )

        results['overall_success'] = market_success and (
            news_success or results['collections']['news_data'].get('skipped', False)) and validation_success

        # Save results
        self.save_results(results)

        # Print final summary
        self.print_final_summary(results)

        return results

    def save_results(self, results: dict):
        """Save test results to file."""
        try:
            with open(self.results_file, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Results saved to: {self.results_file}")
        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    def print_final_summary(self, results: dict):
        """Print comprehensive final summary."""
        logger.info("\n" + "=" * 80)
        logger.info("🎯 FINAL TEST COLLECTION SUMMARY")
        logger.info("=" * 80)

        logger.info(f"Test Period: {results['test_period']}")
        logger.info(f"Total Duration: {results['total_duration']}")
        logger.info(f"Overall Success: {'✅ PASSED' if results['overall_success'] else '❌ FAILED'}")

        logger.info("\n📊 COLLECTION RESULTS:")

        # Market data summary
        market = results['collections']['market_data']
        if market['success']:
            logger.info(
                f"  Market Data: ✅ {market.get('successful_collections', 0)}/{market.get('total_requests', 7)} tickers")
        else:
            logger.info(f"  Market Data: ❌ Failed - {market.get('error', 'Unknown error')}")

        # News data summary
        news = results['collections']['news_data']
        if news.get('skipped'):
            logger.info(f"  News Data: ⏭️ Skipped due to market data failure")
        elif news['success']:
            logger.info(
                f"  News Data: ✅ {news.get('successful_collections', 0)} tickers, Quota: {news.get('quota_usage', 'Unknown')}")
        else:
            logger.info(f"  News Data: ❌ Failed - {news.get('error', 'Unknown error')}")

        # Validation summary
        validation = results['validation']
        market_val = validation.get('market_data_validation', {})
        integration = validation.get('integration_tests', {})

        logger.info("\n✅ VALIDATION RESULTS:")
        logger.info(
            f"  Cache Structure: {'✅' if market_val.get('cache_directory_exists') else '❌'}")
        logger.info(
            f"  Polygon Tool Integration: {'✅' if integration.get('polygon_tool_test') else '❌'}")
        logger.info(f"  News Tool Integration: {'✅' if integration.get('news_tool_test') else '❌'}")

        if results['overall_success']:
            logger.info("\n🎉 TEST COLLECTION SUCCESSFUL!")
            logger.info("Ready to proceed with full-scale MAG7 data collection")
            logger.info("Next step: Run full Q2 2025 collection service")
        else:
            logger.info("\n⚠️ TEST COLLECTION ISSUES DETECTED")
            logger.info("Review errors above before proceeding")

        logger.info("=" * 80)


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description='MAG7 Test Week Data Collection')
    parser.add_argument('--market-only', action='store_true',
                        help='Collect only market data (skip news)')
    parser.add_argument('--news-only', action='store_true',
                        help='Collect only news data (skip market)')
    parser.add_argument('--validate-only', action='store_true',
                        help='Only run validation (skip collection)')

    args = parser.parse_args()

    try:
        collector = MAG7TestCollection()

        if args.validate_only:
            results = collector.validate_cache_integration()
            print("\n✅ VALIDATION COMPLETE")
        elif args.market_only:
            results = collector.run_market_data_collection()
            print("\n📈 MARKET DATA COLLECTION COMPLETE")
        elif args.news_only:
            results = collector.run_news_collection()
            print("\n📰 NEWS DATA COLLECTION COMPLETE")
        else:
            # Full test collection
            results = collector.run_full_test_collection()

        # Exit code based on success
        if results.get('overall_success', False) or args.validate_only or args.market_only or args.news_only:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n⏹️ Collection interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
