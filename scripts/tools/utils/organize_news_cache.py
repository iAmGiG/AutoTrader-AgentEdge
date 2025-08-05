#!/usr/bin/env python3
"""
Organize existing news cache into historical vs recent categories
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import json
import shutil
from datetime import datetime
from collections import defaultdict

def organize_cache_by_content_date():
    """Organize cache files based on actual article publication dates"""
    print("📁 Organizing News Cache by Content Date")
    print("=" * 45)
    
    cache_dir = "./.cache/news/google_search/"
    
    if not os.path.exists(cache_dir):
        print("❌ No cache directory found")
        return
    
    # Create organized structure
    historical_dir = os.path.join(cache_dir, "historical_2022")
    recent_dir = os.path.join(cache_dir, "recent_2024_2025")
    mixed_dir = os.path.join(cache_dir, "mixed_dates")
    
    os.makedirs(historical_dir, exist_ok=True)
    os.makedirs(recent_dir, exist_ok=True)
    os.makedirs(mixed_dir, exist_ok=True)
    
    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json') and not os.path.isdir(os.path.join(cache_dir, f))]
    
    print(f"📊 Processing {len(cache_files)} cache files...")
    
    stats = {
        'historical_2022': 0,
        'recent_2024_2025': 0,
        'mixed_dates': 0,
        'empty_files': 0,
        'total_articles_historical': 0,
        'total_articles_recent': 0
    }
    
    for filename in cache_files:
        filepath = os.path.join(cache_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                cache_data = json.load(f)
            
            articles = cache_data.get('results', [])
            
            if not articles:
                stats['empty_files'] += 1
                continue
            
            # Analyze article dates
            date_counts = {'2022': 0, '2023': 0, '2024+': 0, 'unknown': 0}
            
            for article in articles:
                published_date = article.get('published_date')
                
                try:
                    if published_date and str(published_date) != 'nan':
                        if isinstance(published_date, str):
                            parsed_date = datetime.strptime(published_date.split()[0], '%Y-%m-%d')
                        else:
                            parsed_date = published_date
                        
                        year = parsed_date.year
                        if year == 2022:
                            date_counts['2022'] += 1
                        elif year == 2023:
                            date_counts['2023'] += 1
                        elif year >= 2024:
                            date_counts['2024+'] += 1
                        else:
                            date_counts['unknown'] += 1
                    else:
                        date_counts['unknown'] += 1
                except:
                    date_counts['unknown'] += 1
            
            # Categorize based on predominant content
            total_with_dates = sum(date_counts.values()) - date_counts['unknown']
            
            if total_with_dates == 0:
                # No valid dates - put in mixed
                destination_dir = mixed_dir
                category = 'mixed_dates'
            elif date_counts['2022'] / total_with_dates >= 0.6:
                # Majority 2022 content
                destination_dir = historical_dir
                category = 'historical_2022'
                stats['total_articles_historical'] += date_counts['2022']
            elif date_counts['2024+'] / total_with_dates >= 0.6:
                # Majority recent content
                destination_dir = recent_dir
                category = 'recent_2024_2025'
                stats['total_articles_recent'] += date_counts['2024+']
            else:
                # Mixed content
                destination_dir = mixed_dir
                category = 'mixed_dates'
            
            # Move file to appropriate directory
            destination_path = os.path.join(destination_dir, filename)
            shutil.move(filepath, destination_path)
            
            stats[category] += 1
            
            print(f"📄 {filename[:50]}...")
            print(f"   2022: {date_counts['2022']}, 2023: {date_counts['2023']}, 2024+: {date_counts['2024+']}, Unknown: {date_counts['unknown']}")
            print(f"   → Moved to: {category}")
            
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
    
    return stats

def create_cache_summary():
    """Create summary of organized cache"""
    print(f"\n📊 Creating Cache Organization Summary")
    print("=" * 40)
    
    cache_dir = "./.cache/news/google_search/"
    
    # Count files in each category
    historical_dir = os.path.join(cache_dir, "historical_2022")
    recent_dir = os.path.join(cache_dir, "recent_2024_2025")
    mixed_dir = os.path.join(cache_dir, "mixed_dates")
    
    summary = {
        'historical_2022': len([f for f in os.listdir(historical_dir) if f.endswith('.json')]) if os.path.exists(historical_dir) else 0,
        'recent_2024_2025': len([f for f in os.listdir(recent_dir) if f.endswith('.json')]) if os.path.exists(recent_dir) else 0,
        'mixed_dates': len([f for f in os.listdir(mixed_dir) if f.endswith('.json')]) if os.path.exists(mixed_dir) else 0
    }
    
    # Sample content from each category
    for category, count in summary.items():
        category_dir = os.path.join(cache_dir, category)
        print(f"\n📁 {category.replace('_', ' ').title()}: {count} files")
        
        if count > 0 and os.path.exists(category_dir):
            sample_files = [f for f in os.listdir(category_dir) if f.endswith('.json')][:2]
            
            for sample_file in sample_files:
                sample_path = os.path.join(category_dir, sample_file)
                try:
                    with open(sample_path, 'r') as f:
                        sample_data = json.load(f)
                    
                    articles = sample_data.get('results', [])
                    if articles:
                        sample_article = articles[0]
                        title = sample_article.get('title', 'No title')
                        source = sample_article.get('source', 'Unknown').replace('Google Search - ', '')
                        date = sample_article.get('published_date', 'No date')
                        
                        print(f"   Sample: [{source}] {title[:60]}...")
                        print(f"           Date: {date}")
                
                except Exception as e:
                    continue
    
    return summary

def create_usage_recommendations():
    """Provide recommendations for using organized cache"""
    print(f"\n💡 Cache Usage Recommendations")
    print("=" * 35)
    
    print(f"🎯 Historical 2022 Cache:")
    print(f"   - Use for backtesting October 2022 period")
    print(f"   - Contains actual historical news context")
    print(f"   - Good for sentiment analysis of past events")
    print(f"   - Limited volume but high historical accuracy")
    
    print(f"\n📰 Recent 2024-2025 Cache:")
    print(f"   - Use for current market sentiment analysis")
    print(f"   - Contains fresh financial news and analysis")
    print(f"   - Good for testing current trading strategies")
    print(f"   - High volume and current relevance")
    
    print(f"\n🔄 Mixed Dates Cache:")
    print(f"   - Contains retrospective analysis articles")
    print(f"   - May include historical commentary from recent perspectives")
    print(f"   - Useful for understanding market evolution")
    print(f"   - Requires individual article date verification")
    
    print(f"\n🚀 Next Steps:")
    print(f"   1. Use historical cache for October 2022 backtests")
    print(f"   2. Leverage recent cache for current strategy validation")
    print(f"   3. Consider expanding historical capture with improved search")
    print(f"   4. Build targeted cache for other key historical periods")

def main():
    """Main organization function"""
    print("🗂️  News Cache Organization")
    print("=" * 30)
    
    # Organize existing cache
    stats = organize_cache_by_content_date()
    
    if stats:
        print(f"\n✅ Cache Organization Complete!")
        print(f"📊 Organization Statistics:")
        for category, count in stats.items():
            if isinstance(count, int):
                print(f"   {category.replace('_', ' ').title()}: {count}")
        
        # Create summary
        summary = create_cache_summary()
        
        # Provide recommendations
        create_usage_recommendations()
        
        print(f"\n🎉 Cache is now organized and ready for targeted use!")
    else:
        print(f"❌ No cache files found to organize")

if __name__ == "__main__":
    main()