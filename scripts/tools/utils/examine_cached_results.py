#!/usr/bin/env python3
"""
Examine cached Google Search results to see what articles we actually captured
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import json
import pandas as pd
from datetime import datetime
from collections import defaultdict

def examine_cache_files():
    """Examine what's in our cached search results"""
    print("🔍 Examining Cached Google Search Results")
    print("=" * 50)
    
    cache_dir = "./.cache/news/google_search/"
    
    if not os.path.exists(cache_dir):
        print("❌ No cache directory found")
        return
    
    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
    october_files = [f for f in cache_files if '2022-10' in f]
    
    print(f"📊 Cache Overview:")
    print(f"   Total cache files: {len(cache_files)}")
    print(f"   October 2022 files: {len(october_files)}")
    
    # Analyze a sample of files
    sample_files = october_files[:10]  # Look at first 10
    
    total_articles = 0
    articles_by_ticker = defaultdict(list)
    articles_by_source = defaultdict(int)
    sample_headlines = []
    
    for filename in sample_files:
        filepath = os.path.join(cache_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                cache_data = json.load(f)
            
            # Extract ticker from filename
            ticker = "Unknown"
            for t in ['TSLA', 'META', 'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN']:
                if t in filename:
                    ticker = t
                    break
            
            articles = cache_data.get('results', [])
            total_articles += len(articles)
            
            print(f"\n📄 {filename[:60]}...")
            print(f"   Ticker: {ticker}")
            print(f"   Articles: {len(articles)}")
            print(f"   Date range: {cache_data.get('start_date')} to {cache_data.get('end_date')}")
            
            # Analyze articles in this file
            if articles:
                for article in articles[:3]:  # Show first 3 from each file
                    title = article.get('title', 'No title')
                    source = article.get('source', 'Unknown source')
                    url = article.get('url', '')
                    relevance = article.get('relevance_score', 0)
                    published = article.get('published_date', 'Unknown date')
                    
                    # Count sources
                    source_clean = source.replace('Google Search - ', '')
                    articles_by_source[source_clean] += 1
                    
                    # Store for ticker analysis
                    articles_by_ticker[ticker].append({
                        'title': title,
                        'source': source_clean,
                        'relevance': relevance,
                        'published': published,
                        'url': url
                    })
                    
                    # Show sample
                    print(f"     • [{source_clean}] {title[:70]}...")
                    print(f"       Relevance: {relevance:.2f}, Date: {published}")
                
                if len(articles) > 3:
                    print(f"     ... and {len(articles) - 3} more articles")
        
        except Exception as e:
            print(f"   ❌ Error reading {filename}: {e}")
    
    return total_articles, articles_by_ticker, articles_by_source

def analyze_article_quality(articles_by_ticker, articles_by_source):
    """Analyze the quality and distribution of captured articles"""
    print(f"\n📊 Article Quality Analysis")
    print("=" * 30)
    
    # Source distribution
    print(f"🏢 Articles by Source:")
    sorted_sources = sorted(articles_by_source.items(), key=lambda x: x[1], reverse=True)
    for source, count in sorted_sources:
        print(f"   {source}: {count} articles")
    
    # Ticker distribution
    print(f"\n📈 Articles by Ticker:")
    for ticker, articles in articles_by_ticker.items():
        if articles:
            avg_relevance = sum(a['relevance'] for a in articles) / len(articles)
            print(f"   {ticker}: {len(articles)} articles (avg relevance: {avg_relevance:.2f})")
    
    # Show highest relevance articles
    print(f"\n🎯 Highest Relevance Articles:")
    all_articles = []
    for ticker, articles in articles_by_ticker.items():
        for article in articles:
            article['ticker'] = ticker
            all_articles.append(article)
    
    # Sort by relevance
    top_articles = sorted(all_articles, key=lambda x: x['relevance'], reverse=True)[:10]
    
    for i, article in enumerate(top_articles, 1):
        print(f"   {i}. [{article['ticker']}] {article['title'][:60]}...")
        print(f"      Source: {article['source']}, Relevance: {article['relevance']:.2f}")

def show_sample_search_queries():
    """Show what search queries we actually used"""
    print(f"\n🔍 Sample Search Queries Used:")
    print("=" * 35)
    
    cache_dir = "./.cache/news/google_search/"
    cache_files = [f for f in os.listdir(cache_dir) if '2022-10' in f]
    
    for filename in cache_files[:5]:
        filepath = os.path.join(cache_dir, filename)
        try:
            with open(filepath, 'r') as f:
                cache_data = json.load(f)
            
            query = cache_data.get('query', 'No query stored')
            print(f"📋 {query}")
            
        except Exception as e:
            continue

def examine_specific_ticker_results(ticker='TSLA'):
    """Look in detail at results for a specific ticker"""
    print(f"\n🔍 Deep Dive: {ticker} October 2022 Articles")
    print("=" * 45)
    
    cache_dir = "./.cache/news/google_search/"
    cache_files = [f for f in os.listdir(cache_dir) if ticker in f and '2022-10' in f]
    
    all_articles = []
    
    for filename in cache_files:
        filepath = os.path.join(cache_dir, filename)
        try:
            with open(filepath, 'r') as f:
                cache_data = json.load(f)
            
            articles = cache_data.get('results', [])
            date_range = f"{cache_data.get('start_date')} to {cache_data.get('end_date')}"
            
            for article in articles:
                article['date_range'] = date_range
                all_articles.append(article)
        
        except Exception as e:
            continue
    
    print(f"📊 Found {len(all_articles)} total {ticker} articles across all date ranges")
    
    if all_articles:
        # Group by source
        by_source = defaultdict(list)
        for article in all_articles:
            source = article.get('source', 'Unknown').replace('Google Search - ', '')
            by_source[source].append(article)
        
        print(f"\n🏢 {ticker} articles by source:")
        for source, articles in by_source.items():
            print(f"   {source}: {len(articles)} articles")
        
        # Show some interesting headlines
        print(f"\n📰 Interesting {ticker} headlines found:")
        
        # Sort by relevance
        top_articles = sorted(all_articles, key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        for i, article in enumerate(top_articles[:8], 1):
            title = article.get('title', 'No title')
            source = article.get('source', 'Unknown').replace('Google Search - ', '')
            relevance = article.get('relevance_score', 0)
            date_range = article.get('date_range', 'Unknown period')
            
            print(f"   {i}. [{source}] {title}")
            print(f"      Period: {date_range}, Relevance: {relevance:.2f}")
            
            # Show snippet if available
            snippet = article.get('summary', '')
            if snippet and len(snippet) > 20:
                snippet_clean = snippet[:100] + "..." if len(snippet) > 100 else snippet
                print(f"      Summary: {snippet_clean}")
            print()

def main():
    """Main examination function"""
    total_articles, articles_by_ticker, articles_by_source = examine_cache_files()
    
    if total_articles > 0:
        analyze_article_quality(articles_by_ticker, articles_by_source)
        show_sample_search_queries()
        examine_specific_ticker_results('TSLA')
        examine_specific_ticker_results('META')
        
        print(f"\n🎉 Cache Examination Complete!")
        print(f"   Total articles analyzed: {total_articles}")
        print(f"   Premium sources working: {len(articles_by_source)} different sources")
        print(f"   Ready for sentiment analysis and backtesting!")
    else:
        print("❌ No articles found in cache")

if __name__ == "__main__":
    main()