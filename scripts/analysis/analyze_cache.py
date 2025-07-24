#!/usr/bin/env python3
"""Analyze cached market data to understand coverage."""

import sys
import os
import json
import glob
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))


def analyze_market_cache(cache_dir: str = ".cache/market_data"):
    """Analyze cached market data files.

    :param cache_dir: Directory containing cache files
    :return: Dictionary with analysis results
    """
    cache_files = glob.glob(f"{cache_dir}/*.json")

    print(f"\n📊 Analyzing {len(cache_files)} cached market data files...")

    # Track coverage by symbol and date range
    symbol_coverage = defaultdict(list)
    date_coverage = defaultdict(set)
    sources = defaultdict(int)

    for cache_file in cache_files:
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            symbol = data.get('symbol', 'UNKNOWN')
            start = data.get('start', '')
            end = data.get('end', '')
            source = data.get('source', 'unknown')

            symbol_coverage[symbol].append({
                'start': start,
                'end': end,
                'source': source,
                'file': os.path.basename(cache_file)
            })

            # Track which dates we have data for
            if start and end:
                date_coverage[symbol].add((start, end))

            sources[source] += 1

        except Exception as e:
            print(f"Error reading {cache_file}: {e}")

    return {
        'total_files': len(cache_files),
        'symbols': dict(symbol_coverage),
        'sources': dict(sources),
        'unique_symbols': len(symbol_coverage)
    }


def analyze_news_cache(cache_dir: str = ".cache/news_data"):
    """Analyze cached news data files.

    :param cache_dir: Directory containing cache files
    :return: Dictionary with analysis results
    """
    cache_files = glob.glob(f"{cache_dir}/*.json")

    print(f"\n📰 Analyzing {len(cache_files)} cached news data files...")

    # Track coverage
    keyword_coverage = defaultdict(int)
    ticker_coverage = defaultdict(int)

    for cache_file in cache_files:
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # Extract query parameters from cached data
            if 'query' in data:
                query = data['query']
                if 'keywords' in query:
                    keyword_coverage[query['keywords']] += 1
                if 'ticker' in query:
                    ticker_coverage[query['ticker']] += 1

        except Exception as e:
            print(f"Error reading {cache_file}: {e}")

    return {
        'total_files': len(cache_files),
        'keywords': dict(keyword_coverage),
        'tickers': dict(ticker_coverage)
    }


def print_coverage_report(market_analysis: dict, news_analysis: dict):
    """Print a formatted coverage report."""

    print("\n" + "=" * 60)
    print("CACHE COVERAGE REPORT")
    print("=" * 60)

    # Market data coverage
    print(f"\n📈 Market Data Cache:")
    print(f"   Total cache files: {market_analysis['total_files']}")
    print(f"   Unique symbols: {market_analysis['unique_symbols']}")
    print(
        f"   Data sources: {', '.join(f'{k}({v})' for k, v in market_analysis['sources'].items())}")

    # List symbols with most coverage
    print(f"\n   Top symbols by cache entries:")
    symbol_counts = [(symbol, len(entries))
                     for symbol, entries in market_analysis['symbols'].items()]
    for symbol, count in sorted(symbol_counts, key=lambda x: x[1], reverse=True)[:10]:
        print(f"   - {symbol}: {count} date ranges cached")

    # News data coverage
    print(f"\n📰 News Data Cache:")
    print(f"   Total cache files: {news_analysis['total_files']}")
    print(f"   Unique tickers: {len(news_analysis['tickers'])}")

    if news_analysis['tickers']:
        print(f"\n   Top tickers by cache entries:")
        for ticker, count in sorted(news_analysis['tickers'].items(),
                                    key=lambda x: x[1], reverse=True)[:10]:
            print(f"   - {ticker}: {count} queries cached")


def find_date_coverage(symbol: str, market_analysis: dict):
    """Find which dates we have cached for a symbol."""

    if symbol not in market_analysis['symbols']:
        return []

    coverage = []
    for entry in market_analysis['symbols'][symbol]:
        coverage.append({
            'range': f"{entry['start']} to {entry['end']}",
            'source': entry['source']
        })

    return coverage


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze cached data coverage')
    parser.add_argument('--symbol', '-s', type=str, help='Check coverage for specific symbol')
    parser.add_argument('--market-dir', type=str, default='.cache/market_data',
                        help='Market data cache directory')
    parser.add_argument('--news-dir', type=str, default='.cache/news_data',
                        help='News data cache directory')

    args = parser.parse_args()

    # Analyze caches
    market_analysis = analyze_market_cache(args.market_dir)
    news_analysis = analyze_news_cache(args.news_dir)

    # Print report
    print_coverage_report(market_analysis, news_analysis)

    # Check specific symbol if requested
    if args.symbol:
        symbol = args.symbol.upper()
        print(f"\n\n📊 Coverage for {symbol}:")

        coverage = find_date_coverage(symbol, market_analysis)
        if coverage:
            print(f"   Found {len(coverage)} cached date ranges:")
            for entry in coverage:
                print(f"   - {entry['range']} (source: {entry['source']})")
        else:
            print(f"   No cached data found for {symbol}")

    # Save analysis to file
    output_file = f".cache/cache_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'market_data': market_analysis,
            'news_data': news_analysis
        }, f, indent=2)

    print(f"\n💾 Analysis saved to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
