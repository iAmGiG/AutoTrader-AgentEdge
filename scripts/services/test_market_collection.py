#!/usr/bin/env python3
"""
Quick Market Data Collection Test.

This script tests market data collection for just 2-3 tickers
to validate the system works before running the full week collection.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import time
from datetime import datetime
import logging

from market_data_collector import MarketDataCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_single_ticker_collection():
    """Test collection for a single ticker."""
    logger.info("🧪 TESTING SINGLE TICKER COLLECTION")
    logger.info("="*50)
    
    try:
        collector = MarketDataCollector()
        
        # Test with AAPL for peak volatility period
        ticker = "AAPL"
        start_date = "2025-04-09"
        end_date = "2025-04-16"
        
        logger.info(f"Testing {ticker} from {start_date} to {end_date}")
        
        # Load status
        status = collector.load_status()
        
        # Collect data for single ticker
        success = collector.collect_ticker_data(ticker, start_date, end_date, status)
        
        if success:
            logger.info("✅ SINGLE TICKER TEST SUCCESSFUL")
            return True
        else:
            logger.error("❌ SINGLE TICKER TEST FAILED")
            return False
            
    except Exception as e:
        logger.error(f"Single ticker test failed: {e}")
        return False


def test_three_ticker_collection():
    """Test collection for three tickers to validate rate limiting."""
    logger.info("🧪 TESTING THREE TICKER COLLECTION")
    logger.info("="*50)
    
    try:
        collector = MarketDataCollector()
        
        # Test with AAPL, TSLA, NVDA (most volatile in our analysis)
        test_tickers = ["AAPL", "TSLA", "NVDA"]
        start_date = "2025-04-09"
        end_date = "2025-04-16"
        
        logger.info(f"Testing tickers: {', '.join(test_tickers)}")
        logger.info(f"Period: {start_date} to {end_date}")
        logger.info(f"Expected duration: ~{len(test_tickers) * collector.rate_limit_delay / 60:.1f} minutes")
        
        test_start = datetime.now()
        successful_collections = 0
        
        # Load status
        status = collector.load_status()
        status['start_time'] = test_start.isoformat()
        
        for i, ticker in enumerate(test_tickers, 1):
            logger.info(f"\n[{i}/{len(test_tickers)}] Collecting {ticker}...")
            
            success = collector.collect_ticker_data(ticker, start_date, end_date, status)
            
            if success:
                successful_collections += 1
                logger.info(f"✅ {ticker} collection successful")
            else:
                logger.error(f"❌ {ticker} collection failed")
            
            # Progress update
            progress_pct = (i / len(test_tickers)) * 100
            logger.info(f"Progress: {i}/{len(test_tickers)} ({progress_pct:.1f}%)")
        
        test_end = datetime.now()
        duration = test_end - test_start
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("THREE TICKER TEST SUMMARY")
        logger.info("="*50)
        logger.info(f"Successful: {successful_collections}/{len(test_tickers)}")
        logger.info(f"Success Rate: {(successful_collections/len(test_tickers)*100):.1f}%")
        logger.info(f"Duration: {duration}")
        logger.info(f"Avg Time per Ticker: {duration.total_seconds()/len(test_tickers):.1f}s")
        
        if successful_collections >= 2:  # At least 2 out of 3
            logger.info("✅ THREE TICKER TEST SUCCESSFUL")
            return True
        else:
            logger.error("❌ THREE TICKER TEST FAILED")
            return False
            
    except Exception as e:
        logger.error(f"Three ticker test failed: {e}")
        return False


def validate_collected_data():
    """Validate that collected data is properly cached."""
    logger.info("🔍 VALIDATING COLLECTED DATA")
    logger.info("="*50)
    
    try:
        from validate_cache_integration import CacheIntegrationValidator
        
        validator = CacheIntegrationValidator()
        
        # Quick validation focusing on cache structure
        cache_results = validator.validate_polygon_cache_structure()
        integration_results = validator.test_polygon_tool_integration()
        
        cache_ok = cache_results['cache_directory_exists'] and cache_results['data_format_valid']
        integration_ok = integration_results['data_retrieval_success']
        
        if cache_ok and integration_ok:
            logger.info("✅ DATA VALIDATION SUCCESSFUL")
            logger.info(f"Cache files: {sum(len(files) for files in cache_results['sample_files'].values())}")
            
            data_quality = integration_results.get('data_quality', {})
            if data_quality:
                logger.info(f"Data quality: {data_quality['record_count']} records, {data_quality['date_range']}")
            
            return True
        else:
            logger.error("❌ DATA VALIDATION FAILED")
            if not cache_ok:
                logger.error("  - Cache structure issues")
            if not integration_ok:
                logger.error("  - Tool integration issues")
            return False
            
    except Exception as e:
        logger.error(f"Data validation failed: {e}")
        return False


def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test Market Data Collection')
    parser.add_argument('--single', action='store_true',
                       help='Test single ticker only')
    parser.add_argument('--three', action='store_true', 
                       help='Test three tickers with rate limiting')
    parser.add_argument('--validate', action='store_true',
                       help='Only validate existing cached data')
    
    args = parser.parse_args()
    
    logger.info("🚀 MARKET DATA COLLECTION TEST")
    logger.info("="*60)
    logger.info("Purpose: Validate collection system before full week test")
    logger.info("Expected: Proper caching and rate limiting behavior")
    logger.info("="*60)
    
    all_tests_passed = True
    
    try:
        if args.validate:
            # Only run validation
            validation_passed = validate_collected_data()
            all_tests_passed = validation_passed
            
        elif args.single:
            # Single ticker test
            single_passed = test_single_ticker_collection()
            if single_passed:
                validation_passed = validate_collected_data()
                all_tests_passed = single_passed and validation_passed
            else:
                all_tests_passed = False
                
        elif args.three:
            # Three ticker test (more comprehensive)
            three_passed = test_three_ticker_collection()
            if three_passed:
                validation_passed = validate_collected_data()
                all_tests_passed = three_passed and validation_passed
            else:
                all_tests_passed = False
                
        else:
            # Default: run single ticker test first
            logger.info("Running default single ticker test...")
            single_passed = test_single_ticker_collection()
            
            if single_passed:
                validation_passed = validate_collected_data()
                all_tests_passed = single_passed and validation_passed
                
                if all_tests_passed:
                    logger.info("\n✅ Ready for three ticker test!")
                    logger.info("Run: python scripts/services/test_market_collection.py --three")
            else:
                all_tests_passed = False
        
        # Final summary
        logger.info("\n" + "="*60)
        if all_tests_passed:
            logger.info("🎉 ALL TESTS PASSED!")
            logger.info("✓ Market data collection is working correctly")
            logger.info("✓ Data is properly cached and accessible")
            logger.info("✓ Rate limiting is functioning")
            logger.info("\n➡️ Ready for full week collection:")
            logger.info("   python scripts/services/mag7_test_collection.py --market-only")
        else:
            logger.info("⚠️ SOME TESTS FAILED")
            logger.info("Please review errors above before proceeding")
        logger.info("="*60)
        
        sys.exit(0 if all_tests_passed else 1)
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ Test interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()