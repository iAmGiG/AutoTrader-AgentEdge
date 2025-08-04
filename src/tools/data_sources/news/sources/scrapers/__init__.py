"""
Web Scraping News Sources

News sources accessed through HTML parsing and web scraping.
These sources parse web pages directly and may be subject to structure changes.
"""

from .finviz_historical_scraper import (
    fetch_finviz_mag7_news,
    fetch_finviz_stock_news,
    finviz_mag7_news_tool,
    finviz_stock_news_tool
)

from .yahoo_scraper_tool import (
    fetch_yahoo_finance_news,
    yahoo_finance_scraper_tool
)

__all__ = [
    'fetch_finviz_mag7_news',
    'fetch_finviz_stock_news',
    'finviz_mag7_news_tool',
    'finviz_stock_news_tool',
    'fetch_yahoo_finance_news',
    'yahoo_finance_scraper_tool'
]