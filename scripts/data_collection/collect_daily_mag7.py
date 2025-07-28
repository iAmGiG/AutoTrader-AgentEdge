#!/usr/bin/env python3
"""
Daily MAG7 Data Collection Script

Collects real-time quotes for MAG7 stocks using FMP API and caches them
for future backtesting. Designed to run daily to build historical dataset.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import json
import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.data_sources.market.fmp_tool import FMPTool
from src.tools.cache.market_data_cache import MarketDataCache
from config.config_loader import ConfigLoader

# MAG7 stocks
MAG7_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

class DailyMAG7Collector:
    """Collects daily data for MAG7 stocks using FMP API."""
    
    def __init__(self):
        """Initialize collector with FMP tool and cache."""
        try:
            # FMPTool loads its own config
            self.fmp_tool = FMPTool()
            self.cache = MarketDataCache()
            self.collection_log = []
            
        except Exception as e:
            print(f"❌ Failed to initialize collector: {e}")
            raise
    
    def collect_quotes(self, symbols: list = None) -> dict:
        """Collect real-time quotes for specified symbols."""
        if symbols is None:
            symbols = MAG7_STOCKS
            
        print(f"📊 Collecting quotes for {len(symbols)} symbols...")
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'symbols': symbols,
            'data': {},
            'errors': {}
        }
        
        # Collect individual quotes (more reliable than batch)
        for symbol in symbols:
            try:
                print(f"  📈 Fetching {symbol}...")
                quote_df = self.fmp_tool.fetch_quote(symbol)
                
                if not quote_df.empty:
                    # Convert to dict for storage
                    quote_data = quote_df.iloc[0].to_dict()
                    results['data'][symbol] = quote_data
                    
                    # Cache the data
                    today = datetime.now().strftime('%Y-%m-%d')
                    
                    # Store in cache as single-day DataFrame
                    cache_df = pd.DataFrame([{
                        'Date': today,
                        'Open': quote_data.get('open', 0),
                        'High': quote_data.get('dayHigh', 0),
                        'Low': quote_data.get('dayLow', 0),
                        'Close': quote_data.get('price', 0),
                        'Volume': quote_data.get('volume', 0),
                        'Symbol': symbol
                    }])
                    
                    # Set index to date for cache compatibility
                    cache_df.index = pd.to_datetime([today])
                    
                    # Cache with proper interface
                    self.cache.set(symbol, today, today, 'FMP_QUOTE', cache_df)
                    
                    print(f"    ✅ {symbol}: ${quote_data.get('price', 0):.2f} (Vol: {quote_data.get('volume', 0):,})")
                    
                    # Log successful collection
                    self.collection_log.append({
                        'symbol': symbol,
                        'timestamp': datetime.now().isoformat(),
                        'price': quote_data.get('price', 0),
                        'status': 'success'
                    })
                    
                else:
                    error_msg = f"No data returned for {symbol}"
                    results['errors'][symbol] = error_msg
                    print(f"    ⚠️  {symbol}: {error_msg}")
                    
                    self.collection_log.append({
                        'symbol': symbol,
                        'timestamp': datetime.now().isoformat(),
                        'error': error_msg,
                        'status': 'error'
                    })
                
                # Rate limiting - be respectful to API
                time.sleep(0.2)
                
            except Exception as e:
                error_msg = f"Error fetching {symbol}: {str(e)}"
                results['errors'][symbol] = error_msg
                print(f"    ❌ {symbol}: {error_msg}")
                
                self.collection_log.append({
                    'symbol': symbol,
                    'timestamp': datetime.now().isoformat(),
                    'error': error_msg,
                    'status': 'error'
                })
        
        return results
    
    def save_collection_log(self, results: dict):
        """Save collection results to log file."""
        log_dir = Path(".cache/data_collection")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = log_dir / f"mag7_collection_{today}.json"
        
        # Load existing log if it exists
        if log_file.exists():
            with open(log_file, 'r') as f:
                existing_log = json.load(f)
        else:
            existing_log = {
                'date': today,
                'collections': []
            }
        
        # Add this collection
        existing_log['collections'].append(results)
        
        # Save updated log
        with open(log_file, 'w') as f:
            json.dump(existing_log, f, indent=2, default=str)
        
        print(f"📝 Collection log saved: {log_file}")
    
    def generate_summary(self, results: dict):
        """Generate summary of collection results."""
        successful = len(results['data'])
        failed = len(results['errors'])
        total = len(results['symbols'])
        
        print(f"\n📋 Collection Summary:")
        print(f"   Total symbols: {total}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Success rate: {successful/total*100:.1f}%")
        
        if results['errors']:
            print(f"\n❌ Errors:")
            for symbol, error in results['errors'].items():
                print(f"   {symbol}: {error}")
        
        # Show cached data status
        cache_count = 0
        for symbol in MAG7_STOCKS:
            today = datetime.now().strftime('%Y-%m-%d')
            cached_data = self.cache.get(symbol, today, today, 'FMP_QUOTE')
            if cached_data is not None and not cached_data.empty:
                cache_count += 1
        
        print(f"\n💾 Cache Status:")
        print(f"   Cached quotes today: {cache_count}/{len(MAG7_STOCKS)}")
        
        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'success_rate': successful/total*100,
            'cached': cache_count
        }

def main():
    """Main execution function."""
    print("🚀 Starting daily MAG7 data collection...")
    print(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Initialize collector
        collector = DailyMAG7Collector()
        
        # Collect quotes
        results = collector.collect_quotes()
        
        # Save log
        collector.save_collection_log(results)
        
        # Generate summary
        summary = collector.generate_summary(results)
        
        print(f"\n✅ Daily collection complete!")
        
        # Return results for potential chaining
        return results
        
    except Exception as e:
        print(f"❌ Collection failed: {e}")
        return None

if __name__ == "__main__":
    main()