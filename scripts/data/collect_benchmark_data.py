#!/usr/bin/env python3
"""
Collect benchmark and volatility data for comprehensive V0-V4 analysis.
Fetches VXX, SPY, and QQQ data matching our MAG7 cache structure.
"""

import sys
import os
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.data_sources.market.alpha_vantage_market import AlphaVantageMarketTool
from config.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def collect_benchmark_data():
    """Collect VXX, SPY, and QQQ data for the same date ranges as our MAG7 cache."""

    logger.info("🎯 COLLECTING BENCHMARK & VOLATILITY DATA")
    logger.info("=" * 70)

    # Initialize Alpha Vantage tool (it will load the API key internally)
    config = ConfigLoader()
    av_key = os.getenv('ALPHA_VANTAGE_KEY', config.get('ALPHA_VANTAGE_KEY'))

    if not av_key:
        logger.error("❌ No Alpha Vantage API key found!")
        return

    av_tool = AlphaVantageMarketTool()  # Constructor handles API key loading internally
    logger.info("✅ Alpha Vantage tool initialized")

    # Same quarterly date ranges as MAG7 cache
    quarters = [
        ('2023-11-01', '2023-12-31'),  # Buffer for technical indicators
        ('2024-01-01', '2024-03-31'),  # Q1 2024
        ('2024-04-01', '2024-06-30'),  # Q2 2024
        ('2024-07-01', '2024-09-30'),  # Q3 2024
        ('2024-10-01', '2024-12-31'),  # Q4 2024
        ('2025-01-01', '2025-03-31'),  # Q1 2025
        ('2025-04-01', '2025-06-30'),  # Q2 2025
        ('2025-07-01', '2025-08-14'),  # Q3 2025 (YTD)
    ]

    # Symbols to collect: VXX (volatility), SPY (S&P 500), QQQ (NASDAQ-100)
    symbols = [
        ('VXX', 'VXX Volatility ETF (for V2 Market Fear sentiment)'),
        ('SPY', 'S&P 500 ETF (market benchmark)'),
        ('QQQ', 'NASDAQ-100 ETF (tech benchmark for MAG7 comparison)')
    ]

    logger.info(
        f"📅 Collecting data for {len(symbols)} symbols × {len(quarters)} quarters = {len(symbols) * len(quarters)} total calls")

    total_calls = len(symbols) * len(quarters)
    successful = 0
    errors = 0
    call_count = 0

    for symbol, description in symbols:
        logger.info(f"\n🎯 COLLECTING {symbol}: {description}")
        logger.info("-" * 50)

        for i, (start_date, end_date) in enumerate(quarters, 1):
            call_count += 1
            logger.info(
                f"📊 [{call_count}/{total_calls}] Fetching {symbol}: {start_date} to {end_date}")

            try:
                result = av_tool.fetch_stock_data(symbol, start_date, end_date)

                if result is not None and not result.empty:
                    logger.info(
                        f"✅ Success: {symbol} {start_date} to {end_date} ({len(result)} records)")
                    successful += 1
                else:
                    logger.warning(f"📡 Empty data returned for {symbol} {start_date} to {end_date}")
                    errors += 1

                # Rate limiting - Alpha Vantage: 25 calls/day, 5 calls/minute
                if call_count < total_calls:  # Don't sleep after the last request
                    logger.info("⏰ Rate limiting: sleeping 15s...")
                    time.sleep(15)

            except Exception as e:
                logger.error(f"❌ Error fetching {symbol} {start_date} to {end_date}: {e}")
                errors += 1

                # Continue with rate limiting even on errors
                if call_count < total_calls:
                    time.sleep(15)

    logger.info("\n" + "=" * 70)
    logger.info("✅ BENCHMARK & VOLATILITY DATA COLLECTION COMPLETE!")
    logger.info(f"Successful: {successful}/{total_calls} calls")
    logger.info(f"Errors: {errors}/{total_calls} calls")
    logger.info(f"Success rate: {successful/total_calls*100:.1f}%")

    if successful > 0:
        logger.info(f"\n📊 Data collected and cached:")
        logger.info("  - VXX: Ready for V2 Market Fear sentiment analysis")
        logger.info("  - SPY: S&P 500 benchmark for performance comparison")
        logger.info("  - QQQ: NASDAQ-100 benchmark for MAG7 tech comparison")
        logger.info("\nCheck .cache/market_data/ for *_alpha_vantage.json files")
    else:
        logger.error("❌ No data was successfully collected!")

    # Estimate time taken
    estimated_time = total_calls * 15 / 60  # 15 seconds per call
    logger.info(f"\n⏱️  Estimated runtime: ~{estimated_time:.1f} minutes")


if __name__ == "__main__":
    collect_benchmark_data()
