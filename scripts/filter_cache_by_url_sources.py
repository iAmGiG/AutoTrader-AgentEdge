#!/usr/bin/env python3
"""
Filter news cache to only keep articles from our 4 reliable sources
Extract dates from URLs and organize into monthly buckets
Discard everything else
"""

import json
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from typing import Optional, Dict, List

def extract_date_from_url(url: str) -> Optional[str]:
    """
    Extract date from URL for our 4 reliable sources only
    Returns YYYY-MM-DD or None
    """
    
    # CNBC: /yyyy/mm/dd/
    cnbc_pattern = r'cnbc\.com/(\d{4})/(\d{2})/(\d{2})/'
    match = re.search(cnbc_pattern, url)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    # Bloomberg: /news/articles/yyyy-mm-dd/
    bloomberg_pattern = r'bloomberg\.com/news/articles/(\d{4})-(\d{2})-(\d{2})'
    match = re.search(bloomberg_pattern, url)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    # Reuters: article-name-yyyy-mm-dd/ at the end
    reuters_pattern = r'reuters\.com/.*-(\d{4})-(\d{2})-(\d{2})/?$'
    match = re.search(reuters_pattern, url)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    # Business Wire: /home/YYYYMMDD#####/
    businesswire_pattern = r'businesswire\.com/news/home/(\d{4})(\d{2})(\d{2})\d+/'
    match = re.search(businesswire_pattern, url)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    return None

def is_reliable_source(url: str) -> bool:
    """Check if URL is from one of our 4 reliable sources"""
    reliable_domains = [
        'businesswire.com',
        'reuters.com', 
        'cnbc.com',
        'bloomberg.com'
    ]
    
    for domain in reliable_domains:
        if domain in url:
            return True
    return False

def filter_cache_folder(source_folder: Path, target_folder: Path) -> Dict:
    """
    Filter a cache folder to only reliable sources with URL dates
    Organize into monthly buckets
    """
    
    stats = {
        'files_processed': 0,
        'articles_total': 0,
        'articles_kept': 0,
        'articles_discarded': 0,
        'reliable_sources': 0,
        'url_dates_extracted': 0,
        'monthly_files_created': 0
    }
    
    # Track monthly data: {ticker: {month: [articles]}}
    monthly_data = {}
    
    print(f"🔍 Processing {source_folder.name}")
    
    for json_file in source_folder.rglob('*.json'):
        if json_file.name.endswith('.backup.json'):
            continue
            
        stats['files_processed'] += 1
        
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            articles = data.get('results', [])
            if not isinstance(articles, list):
                continue
                
            stats['articles_total'] += len(articles)
            
            # Get ticker from file path or data
            ticker = 'UNKNOWN'
            parts = json_file.parts
            if len(parts) >= 3 and parts[-2].isupper():
                ticker = parts[-2]
            elif 'ticker' in data:
                ticker = data['ticker'].upper()
            elif articles and 'ticker' in articles[0]:
                ticker = articles[0]['ticker'].upper()
            
            for article in articles:
                url = article.get('url', '')
                if not url:
                    stats['articles_discarded'] += 1
                    continue
                
                # Filter 1: Must be from reliable source
                if not is_reliable_source(url):
                    stats['articles_discarded'] += 1
                    continue
                
                stats['reliable_sources'] += 1
                
                # Filter 2: Must have extractable date from URL
                url_date = extract_date_from_url(url)
                if not url_date:
                    stats['articles_discarded'] += 1
                    continue
                
                stats['url_dates_extracted'] += 1
                
                # Extract year-month for bucketing
                try:
                    date_obj = datetime.strptime(url_date, '%Y-%m-%d')
                    month_key = date_obj.strftime('%Y-%m')
                    
                    # Add to monthly bucket
                    if ticker not in monthly_data:
                        monthly_data[ticker] = {}
                    if month_key not in monthly_data[ticker]:
                        monthly_data[ticker][month_key] = []
                    
                    # Add URL date to article data
                    article['url_extracted_date'] = url_date
                    article['url_extracted_month'] = month_key
                    
                    monthly_data[ticker][month_key].append(article)
                    stats['articles_kept'] += 1
                    
                except ValueError:
                    stats['articles_discarded'] += 1
                    continue
                    
        except Exception as e:
            print(f"  ⚠️  Error reading {json_file}: {e}")
    
    # Write monthly files
    target_folder.mkdir(exist_ok=True)
    
    for ticker, months in monthly_data.items():
        ticker_dir = target_folder / ticker
        ticker_dir.mkdir(exist_ok=True)
        
        for month, articles in months.items():
            if not articles:  # Skip empty months
                continue
                
            month_file = ticker_dir / f"{month}.json"
            
            # Remove duplicates by URL
            unique_articles = []
            seen_urls = set()
            for article in articles:
                url = article.get('url', '')
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_articles.append(article)
            
            # Create clean monthly file
            monthly_file_data = {
                'month': month,
                'ticker': ticker,
                'filtered_at': datetime.now().isoformat(),
                'filter_criteria': 'URL_sources_only',
                'sources_included': ['businesswire.com', 'reuters.com', 'cnbc.com', 'bloomberg.com'],
                'results': unique_articles,
                'articles_count': len(unique_articles),
                'duplicates_removed': len(articles) - len(unique_articles)
            }
            
            with open(month_file, 'w') as f:
                json.dump(monthly_file_data, f, indent=2, default=str)
            
            stats['monthly_files_created'] += 1
            print(f"  ✅ {ticker}/{month}: {len(unique_articles)} articles")
    
    return stats

def main():
    """Filter all cache folders to reliable sources only"""
    
    print("🚀 Filtering Cache to Reliable URL Sources Only")
    print("=" * 70)
    print("Keeping only: Business Wire, Reuters, CNBC, Bloomberg")
    print("Extracting dates from URLs, organizing by month")
    print()
    
    # Source folders to filter (in priority order)
    source_folders = [
        Path('.cache/news_monthly'),
        Path('.cache/news_monthly_wsj'), 
        Path('.cache/news_reorganized'),
    ]
    
    target_folder = Path('.cache/news_filtered')
    
    # Remove existing filtered folder
    if target_folder.exists():
        import shutil
        shutil.rmtree(target_folder)
        print(f"🗑️  Removed existing {target_folder}")
    
    total_stats = {
        'files_processed': 0,
        'articles_total': 0,
        'articles_kept': 0,
        'articles_discarded': 0,
        'reliable_sources': 0,
        'url_dates_extracted': 0,
        'monthly_files_created': 0
    }
    
    # Process each source folder
    for source_folder in source_folders:
        if not source_folder.exists():
            continue
            
        stats = filter_cache_folder(source_folder, target_folder)
        
        # Add to totals
        for key in total_stats:
            total_stats[key] += stats[key]
        
        print(f"\n📊 {source_folder.name} Results:")
        print(f"  • Files processed: {stats['files_processed']}")
        print(f"  • Articles total: {stats['articles_total']}")
        print(f"  • Reliable sources: {stats['reliable_sources']}")
        print(f"  • URL dates extracted: {stats['url_dates_extracted']}")
        print(f"  • Articles kept: {stats['articles_kept']}")
        print(f"  • Articles discarded: {stats['articles_discarded']}")
        print(f"  • Monthly files created: {stats['monthly_files_created']}")
    
    # Final summary
    print(f"\n" + "=" * 70)
    print("✅ FILTERING COMPLETE")
    print("=" * 70)
    
    print(f"\n📈 Overall Results:")
    print(f"  • Files processed: {total_stats['files_processed']}")
    print(f"  • Articles examined: {total_stats['articles_total']}")
    print(f"  • Articles kept: {total_stats['articles_kept']} ({total_stats['articles_kept']/max(total_stats['articles_total'],1)*100:.1f}%)")
    print(f"  • Articles discarded: {total_stats['articles_discarded']} ({total_stats['articles_discarded']/max(total_stats['articles_total'],1)*100:.1f}%)")
    print(f"  • Monthly files created: {total_stats['monthly_files_created']}")
    
    if total_stats['articles_kept'] > 0:
        print(f"\n📁 Clean Cache Structure:")
        print(f"  Location: {target_folder}")
        print(f"  Format: TICKER/YYYY-MM.json")
        print(f"  Sources: Business Wire, Reuters, CNBC, Bloomberg only")
        print(f"  Dates: Extracted from URLs")
        
        # Show sample structure
        print(f"\n📋 Sample Structure:")
        tickers_shown = 0
        for ticker_dir in sorted(target_folder.iterdir()):
            if ticker_dir.is_dir() and tickers_shown < 3:
                files = list(ticker_dir.glob('*.json'))
                if files:
                    print(f"  {ticker_dir.name}/ ({len(files)} months)")
                    for f in sorted(files)[:3]:
                        with open(f) as jf:
                            data = json.load(jf)
                            count = len(data.get('results', []))
                            print(f"    {f.name}: {count} articles")
                    tickers_shown += 1
        
        print(f"\n💡 Next Steps:")
        print(f"  • Update GoogleSearchNewsTool to use {target_folder}")
        print(f"  • Test with clean, filtered cache")
        print(f"  • Remove old cache folders once verified")
        
    else:
        print(f"\n❌ No articles matched criteria!")
        print(f"  • Check if URLs contain expected patterns")
        print(f"  • Verify source domains are correct")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())