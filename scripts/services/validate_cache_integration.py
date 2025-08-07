#!/usr/bin/env python3
"""
Cache Integration Validation Script.

This script validates that the MAG7 data collection services
store data in a format compatible with existing RH2MAS tools.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CacheIntegrationValidator:
    """
    Validates cache integration between collection services and existing tools.
    """

    def __init__(self):
        """Initialize the validator."""
        self.test_ticker = "AAPL"
        self.test_start = "2025-04-09"
        self.test_end = "2025-04-16"

        # Cache directories
        self.polygon_cache_dir = Path('.cache/polygon')
        self.news_cache_dir = Path('.cache/news/google_search')

        logger.info("Cache Integration Validator initialized")

    def validate_polygon_cache_structure(self) -> dict:
        """
        Validate Polygon.io cache structure and format.

        Returns:
            Validation results
        """
        logger.info("Validating Polygon.io cache structure...")

        results = {
            'cache_directory_exists': self.polygon_cache_dir.exists(),
            'subdirectories': {},
            'sample_files': {},
            'data_format_valid': False
        }

        if not results['cache_directory_exists']:
            logger.warning(f"Polygon cache directory not found: {self.polygon_cache_dir}")
            return results

        # Check subdirectories
        for subdir in ['prices', 'news', 'events']:
            subdir_path = self.polygon_cache_dir / subdir
            results['subdirectories'][subdir] = subdir_path.exists()

            if subdir_path.exists():
                files = list(subdir_path.glob('*.json'))
                results['sample_files'][subdir] = [f.name for f in files[:3]]

        # Test data format by loading a sample file
        prices_dir = self.polygon_cache_dir / 'prices'
        if prices_dir.exists():
            sample_files = list(prices_dir.glob('*.json'))
            if sample_files:
                try:
                    import json
                    with open(sample_files[0], 'r') as f:
                        sample_data = json.load(f)

                    # Check if it's a valid DataFrame-like structure
                    if isinstance(sample_data, list) and len(sample_data) > 0:
                        sample_record = sample_data[0]
                        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']

                        if all(col in sample_record for col in required_columns):
                            results['data_format_valid'] = True
                            logger.info("✓ Polygon cache data format is valid")
                        else:
                            logger.warning(
                                f"⚠ Missing columns in cache data: {sample_record.keys()}")
                    else:
                        logger.warning("⚠ Invalid cache data format")

                except Exception as e:
                    logger.error(f"✗ Failed to validate cache format: {e}")

        return results

    def test_polygon_tool_integration(self) -> dict:
        """
        Test that existing Polygon tool can read cached data.

        Returns:
            Integration test results
        """
        logger.info("Testing Polygon tool integration...")

        results = {
            'tool_import_success': False,
            'data_retrieval_success': False,
            'data_quality': {},
            'errors': []
        }

        try:
            # Test tool import
            from src.tools.tools import fetch_polygon_historical_data
            results['tool_import_success'] = True
            logger.info("✓ Successfully imported Polygon tool")

            # Test data retrieval
            data = fetch_polygon_historical_data(
                ticker=self.test_ticker,
                start_date=self.test_start,
                end_date=self.test_end,
                data_type="prices"
            )

            if data and 'prices' in data and len(data['prices']) > 0:
                results['data_retrieval_success'] = True

                # Analyze data quality
                prices = data['prices']
                results['data_quality'] = {
                    'record_count': len(prices),
                    'date_range': f"{prices[0].get('date', 'Unknown')} to {prices[-1].get('date', 'Unknown')}",
                    'has_ohlcv': all(key in prices[0] for key in ['open', 'high', 'low', 'close', 'volume'])
                }

                logger.info(f"✓ Retrieved {len(prices)} price records for {self.test_ticker}")

            else:
                results['errors'].append("No data returned from Polygon tool")
                logger.warning("⚠ Polygon tool returned no data")

        except ImportError as e:
            results['errors'].append(f"Failed to import Polygon tool: {e}")
            logger.error(f"✗ Failed to import Polygon tool: {e}")
        except Exception as e:
            results['errors'].append(f"Polygon tool integration failed: {e}")
            logger.error(f"✗ Polygon tool integration failed: {e}")

        return results

    def test_news_cache_integration(self) -> dict:
        """
        Test news cache structure and integration.

        Returns:
            News integration test results
        """
        logger.info("Testing news cache integration...")

        results = {
            'cache_directory_exists': self.news_cache_dir.exists(),
            'cache_files': [],
            'news_tool_integration': False,
            'errors': []
        }

        if results['cache_directory_exists']:
            cache_files = list(self.news_cache_dir.glob('*.json'))
            results['cache_files'] = [f.name for f in cache_files[-5:]]  # Last 5 files
            logger.info(f"Found {len(cache_files)} news cache files")
        else:
            logger.warning(f"News cache directory not found: {self.news_cache_dir}")

        # Test news tool integration
        try:
            from src.tools.data_sources.news.aggregators.hybrid_historical_news_tool import hybrid_historical_news_tool

            news_df = hybrid_historical_news_tool(
                query=f"{self.test_ticker} stock market crash",
                start_date=self.test_start,
                end_date=self.test_end,
                max_results=5
            )

            if not news_df.empty:
                results['news_tool_integration'] = True
                logger.info(f"✓ Retrieved {len(news_df)} news articles")
            else:
                logger.warning("⚠ News tool returned no data")

        except Exception as e:
            results['errors'].append(f"News tool integration failed: {e}")
            logger.error(f"✗ News tool integration failed: {e}")

        return results

    def test_backtest_compatibility(self) -> dict:
        """
        Test that cached data is compatible with backtest tools.

        Returns:
            Backtest compatibility results
        """
        logger.info("Testing backtest tool compatibility...")

        results = {
            'data_format_compatible': False,
            'date_range_valid': False,
            'required_columns_present': False,
            'errors': []
        }

        try:
            # Test if we can load data in backtest-compatible format
            from src.tools.tools import fetch_polygon_historical_data

            data = fetch_polygon_historical_data(
                ticker=self.test_ticker,
                start_date=self.test_start,
                end_date=self.test_end,
                data_type="prices"
            )

            if data and 'prices' in data:
                prices = data['prices']

                # Convert to DataFrame to test compatibility
                df = pd.DataFrame(prices)

                if not df.empty:
                    # Check required columns for backtesting
                    required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
                    results['required_columns_present'] = all(
                        col in df.columns for col in required_cols)

                    # Check date format
                    if 'date' in df.columns:
                        try:
                            df['date'] = pd.to_datetime(df['date'])
                            results['date_range_valid'] = True
                            logger.info("✓ Date format is valid for backtesting")
                        except Exception as e:
                            results['errors'].append(f"Date format issue: {e}")

                    results['data_format_compatible'] = (
                        results['required_columns_present'] and
                        results['date_range_valid']
                    )

                    if results['data_format_compatible']:
                        logger.info("✓ Data format is compatible with backtest tools")
                    else:
                        logger.warning("⚠ Data format compatibility issues detected")
                else:
                    results['errors'].append("Empty DataFrame returned")
            else:
                results['errors'].append("No price data available for compatibility test")

        except Exception as e:
            results['errors'].append(f"Backtest compatibility test failed: {e}")
            logger.error(f"✗ Backtest compatibility test failed: {e}")

        return results

    def run_full_validation(self) -> dict:
        """
        Run complete cache integration validation.

        Returns:
            Complete validation results
        """
        logger.info("🔍 STARTING COMPLETE CACHE INTEGRATION VALIDATION")
        logger.info("=" * 70)

        validation_start = datetime.now()

        results = {
            'validation_start': validation_start.isoformat(),
            'test_parameters': {
                'test_ticker': self.test_ticker,
                'test_period': f"{self.test_start} to {self.test_end}"
            },
            'polygon_cache': {},
            'polygon_integration': {},
            'news_integration': {},
            'backtest_compatibility': {},
            'overall_success': False
        }

        # Test 1: Polygon cache structure
        logger.info("\n1. Validating Polygon cache structure...")
        results['polygon_cache'] = self.validate_polygon_cache_structure()

        # Test 2: Polygon tool integration
        logger.info("\n2. Testing Polygon tool integration...")
        results['polygon_integration'] = self.test_polygon_tool_integration()

        # Test 3: News integration
        logger.info("\n3. Testing news cache integration...")
        results['news_integration'] = self.test_news_cache_integration()

        # Test 4: Backtest compatibility
        logger.info("\n4. Testing backtest tool compatibility...")
        results['backtest_compatibility'] = self.test_backtest_compatibility()

        # Overall success assessment
        polygon_cache_ok = results['polygon_cache']['cache_directory_exists']
        polygon_integration_ok = results['polygon_integration']['data_retrieval_success']
        backtest_compatible = results['backtest_compatibility']['data_format_compatible']

        results['overall_success'] = (
            polygon_cache_ok and
            polygon_integration_ok and
            backtest_compatible
        )

        # Final summary
        validation_end = datetime.now()
        results['validation_end'] = validation_end.isoformat()
        results['duration'] = str(validation_end - validation_start)

        self.print_validation_summary(results)

        return results

    def print_validation_summary(self, results: dict):
        """Print comprehensive validation summary."""
        logger.info("\n" + "=" * 70)
        logger.info("🎯 CACHE INTEGRATION VALIDATION SUMMARY")
        logger.info("=" * 70)

        logger.info(f"Test Period: {results['test_parameters']['test_period']}")
        logger.info(f"Duration: {results['duration']}")
        logger.info(f"Overall Success: {'✅ PASSED' if results['overall_success'] else '❌ FAILED'}")

        logger.info("\n📊 DETAILED RESULTS:")

        # Polygon cache
        polygon_cache = results['polygon_cache']
        status = "✅" if polygon_cache['cache_directory_exists'] else "❌"
        logger.info(f"  Polygon Cache Structure: {status}")

        # Polygon integration
        polygon_int = results['polygon_integration']
        status = "✅" if polygon_int['data_retrieval_success'] else "❌"
        data_count = polygon_int.get('data_quality', {}).get('record_count', 0)
        logger.info(f"  Polygon Tool Integration: {status} ({data_count} records)")

        # News integration
        news_int = results['news_integration']
        status = "✅" if news_int['news_tool_integration'] else "❌"
        logger.info(f"  News Tool Integration: {status}")

        # Backtest compatibility
        backtest = results['backtest_compatibility']
        status = "✅" if backtest['data_format_compatible'] else "❌"
        logger.info(f"  Backtest Compatibility: {status}")

        if results['overall_success']:
            logger.info("\n🎉 CACHE INTEGRATION VALIDATION SUCCESSFUL!")
            logger.info("✓ Collected data is properly cached and accessible")
            logger.info("✓ Existing tools can read the cached data")
            logger.info("✓ Data format is compatible with backtest system")
            logger.info("\n➡️ Ready to proceed with full MAG7 data collection")
        else:
            logger.info("\n⚠️ CACHE INTEGRATION ISSUES DETECTED")
            logger.info("Please review the detailed results above")

            # Show specific errors
            all_errors = []
            for section in ['polygon_integration', 'news_integration', 'backtest_compatibility']:
                errors = results.get(section, {}).get('errors', [])
                all_errors.extend(errors)

            if all_errors:
                logger.info("\n🐛 ERRORS FOUND:")
                for error in all_errors:
                    logger.info(f"  - {error}")

        logger.info("=" * 70)


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description='Cache Integration Validation')
    parser.add_argument('--ticker', type=str, default='AAPL',
                        help='Ticker to test with (default: AAPL)')
    parser.add_argument('--start-date', type=str, default='2025-04-09',
                        help='Test start date (default: 2025-04-09)')
    parser.add_argument('--end-date', type=str, default='2025-04-16',
                        help='Test end date (default: 2025-04-16)')

    args = parser.parse_args()

    try:
        validator = CacheIntegrationValidator()
        validator.test_ticker = args.ticker
        validator.test_start = args.start_date
        validator.test_end = args.end_date

        results = validator.run_full_validation()

        # Exit with appropriate code
        sys.exit(0 if results['overall_success'] else 1)

    except KeyboardInterrupt:
        logger.info("\n⏹️ Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
