#!/usr/bin/env python3
"""
Test script to verify NewsAPI and Finnhub news sources are properly configured.
This script tests each news source individually and through the unified news tool.
"""

import sys
import os
from datetime import datetime, timedelta
import json
from typing import Dict, List, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.data_sources.news.news_headline_tool import NewsHeadlineTool
from src.tools.data_sources.news.finnhub_tool import FinnHubTool
from src.tools.data_sources.news.unified_news_tool import fetch_unified_news
from src.tools.date_utils import get_processed_date_range, process_date_param
from config.config_loader import ConfigLoader

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BOLD}{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{BLUE}{text:^60}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 60}{RESET}\n")


def print_success(text: str):
    """Print success message in green."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    """Print error message in red."""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str):
    """Print warning message in yellow."""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text: str):
    """Print info message in blue."""
    print(f"{BLUE}ℹ {text}{RESET}")


def check_api_key_status():
    """Check the status of API keys."""
    print_header("API Key Status")
    
    try:
        config = ConfigLoader()
        
        # Check NewsAPI key
        newsapi_key = config.get("NEWSAPI_KEY")
        if newsapi_key and newsapi_key != "your_newsapi_key_here":
            print_success(f"NewsAPI key configured (length: {len(newsapi_key)})")
        else:
            print_error("NewsAPI key not configured or using placeholder")
        
        # Check Finnhub key
        finnhub_key = config.get("FINNHUB_KEY")
        if finnhub_key and finnhub_key != "your_finnhub_api_key_here":
            print_success(f"Finnhub key configured (length: {len(finnhub_key)})")
        else:
            print_error("Finnhub key not configured or using placeholder")
            
    except Exception as e:
        print_error(f"Failed to check API keys: {str(e)}")


def test_newsapi():
    """Test NewsAPI functionality."""
    print_header("Testing NewsAPI")
    
    try:
        # Create NewsHeadlineTool instance
        news_tool = NewsHeadlineTool(source="newsapi")
        print_success("NewsHeadlineTool instance created")
        
        # Test with a technology query
        print_info("Testing with query: 'NVDA'")
        result = news_tool.fetch_data(keyword="NVDA", count=5)
        
        if result is not None and not result.empty:
            print_success(f"Retrieved {len(result)} articles")
            print("\nSample headlines:")
            for idx, row in result.head(3).iterrows():
                print(f"  {idx+1}. {row['Headline'][:80]}...")
                print(f"     Source: {row['Source']}")
                print(f"     Published: {row['Timestamp']}")
                if 'Sentiment Score' in row and row['Sentiment Score']:
                    print(f"     Sentiment Score: {row['Sentiment Score']:.3f}")
                print()
        else:
            print_warning("No articles retrieved (API might be rate limited or key invalid)")
            
        # Test with another query
        print_info("Testing with query: 'technology earnings'")
        result2 = news_tool.fetch_data(keyword="technology earnings", count=5)
        
        if result2 is not None and not result2.empty:
            print_success(f"Retrieved {len(result2)} articles for second query")
        else:
            print_warning("No articles retrieved for second query")
            
    except Exception as e:
        print_error(f"NewsAPI test failed: {str(e)}")
        import traceback
        traceback.print_exc()


def test_finnhub():
    """Test Finnhub functionality."""
    print_header("Testing Finnhub")
    
    try:
        # Create FinnHubTool instance
        finnhub_tool = FinnHubTool()
        print_success("FinnHubTool instance created")
        
        # Calculate date range (last 7 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Test with Apple stock
        print_info(f"Testing news for AAPL ticker filter")
        result = finnhub_tool.fetch_news(
            category="general",
            tickers=["AAPL"],
            count=10
        )
        
        if result is not None and not result.empty:
            print_success(f"Retrieved {len(result)} articles")
            print("\nSample headlines:")
            for idx, row in result.head(3).iterrows():
                print(f"  {idx+1}. {row['Headline'][:80]}...")
                print(f"     Source: {row['Source']}")
                print(f"     Published: {row['Date']}")
                if 'Category' in row and row['Category']:
                    print(f"     Category: {row['Category']}")
                print()
        else:
            print_warning("No articles retrieved (API might be rate limited or key invalid)")
            
        # Test market news
        print_info("Testing general market news")
        market_result = finnhub_tool.fetch_financial_headlines(count=10)
        
        if market_result is not None and not market_result.empty:
            print_success(f"Retrieved {len(market_result)} market news articles")
        else:
            print_warning("No market news retrieved")
            
    except Exception as e:
        print_error(f"Finnhub test failed: {str(e)}")
        import traceback
        traceback.print_exc()


def test_unified_news():
    """Test Unified News Tool functionality."""
    print_header("Testing Unified News Tool")
    
    try:
        # Get date range using date_utils
        start_date, end_date = get_processed_date_range(default_days_back=7)
        
        # Test with multiple sources enabled
        print_info(f"Testing unified news with all sources for 'AAPL' from {start_date} to {end_date}")
        
        result = fetch_unified_news(
            keywords="Apple earnings",
            ticker="AAPL",
            start_date=start_date,
            end_date=end_date,
            sources="newsapi,finnhub,alphavantage",
            count=10
        )
        
        if isinstance(result, dict):
            if 'articles' in result and result['articles']:
                articles = result['articles']
                print_success(f"Retrieved {len(articles)} total articles")
                
                # Count articles by source
                source_counts = {}
                for article in articles:
                    source = article.get('provider', 'Unknown')
                    source_counts[source] = source_counts.get(source, 0) + 1
                
                print("\nArticles by source:")
                for source, count in source_counts.items():
                    print(f"  - {source}: {count} articles")
                
                # Show sample articles
                print("\nSample articles:")
                for i, article in enumerate(articles[:3], 1):
                    print(f"  {i}. {article['title'][:80]}...")
                    print(f"     Provider: {article['provider']}")
                    print(f"     Published: {article['published_date']}")
                    if 'sentiment_score' in article:
                        print(f"     Sentiment: {article['sentiment_label']} ({article['sentiment_score']:.3f})")
                    if 'relevance_score' in article:
                        print(f"     Relevance: {article['relevance_score']:.2f}")
                    print()
                
                # Check for search guidance
                if 'search_guidance' in result and result['search_guidance']:
                    print_warning(f"Search guidance: {result['search_guidance']}")
                    
            else:
                print_warning("No articles retrieved from unified news tool")
                if 'search_guidance' in result:
                    print_info(f"Search guidance: {result['search_guidance']}")
        else:
            print_error("Unexpected result format from unified news tool")
            
    except Exception as e:
        print_error(f"Unified news test failed: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Run all tests."""
    print(f"{BOLD}News Sources Configuration Test{RESET}")
    print(f"Testing at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check API keys first
    check_api_key_status()
    
    # Test individual sources
    test_newsapi()
    test_finnhub()
    
    # Test unified tool
    test_unified_news()
    
    print_header("Test Summary")
    print_info("Tests completed. Check the output above for any errors or warnings.")
    print_info("If you see rate limiting errors, wait a few minutes and try again.")
    print_info("Make sure your API keys are properly configured in config/config.json")


if __name__ == "__main__":
    main()