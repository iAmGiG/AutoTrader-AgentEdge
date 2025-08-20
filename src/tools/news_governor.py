"""
Smart News Sampling Governor for API Quota Management

Reduces Google Search API calls from 252/quarter to 20-50/quarter (80-90% reduction)
while maintaining data quality through intelligent sampling and cache reuse.

Issue #204: Smart News Sampling to reduce Google Search quota usage
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pandas as pd
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NewsSample:
    """Represents a news sampling point with metadata."""
    date: datetime
    symbol: str
    news_data: pd.DataFrame
    cache_key: str
    fetch_timestamp: datetime
    sampling_reason: str  # 'scheduled', 'volatility_spike', 'earnings', etc.


class NewsGovernor:
    """
    Smart news sampling controller that reduces API quota usage while maintaining data quality.
    
    Key Features:
    - Multiple sampling strategies (daily, weekly, bi-weekly, monthly, smart)
    - Intelligent cache reuse between sampling points
    - Volatility-aware adaptive sampling
    - Quota tracking and warnings
    - Performance metrics and optimization suggestions
    """
    
    def __init__(self, 
                 sampling_strategy: str = 'weekly',
                 max_calls_per_test: int = 50,
                 cache_dir: str = '.cache/news_governor',
                 cache_window_days: int = 7,
                 strict_sampling: bool = False):
        """
        Initialize news sampling governor.
        
        Args:
            sampling_strategy: 'daily', 'weekly', 'bi_weekly', 'monthly', 'smart'
            max_calls_per_test: Maximum API calls allowed per test run
            cache_dir: Directory for caching news samples
            cache_window_days: Maximum age of cached news to reuse (default: 7 days)
            strict_sampling: If True, only fetch on sampling days (no cache fallback)
        """
        self.sampling_strategy = sampling_strategy
        self.max_calls_per_test = max_calls_per_test
        self.cache_window_days = cache_window_days
        self.strict_sampling = strict_sampling
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Tracking
        self.api_calls_made = 0
        self.cache_hits = 0
        self.news_samples = {}  # date+symbol -> NewsSample
        self.volatility_data = {}  # For smart sampling
        
        # Load existing samples
        self._load_existing_samples()
        
        logger.info(f"📰 NewsGovernor initialized: {sampling_strategy} sampling, max {max_calls_per_test} calls, {cache_window_days}d cache window")
    
    def should_fetch_news(self, date: datetime, symbol: str, volatility_level: float = None) -> Tuple[bool, str]:
        """
        Determine if we should fetch fresh news for this date/symbol.
        
        Args:
            date: Target date for news
            symbol: Stock symbol  
            volatility_level: Optional VXX level for smart sampling
            
        Returns:
            (should_fetch: bool, reason: str)
        """
        # Check quota limits
        if self.api_calls_made >= self.max_calls_per_test:
            return False, f"quota_exceeded_{self.api_calls_made}"
        
        # Check if we already have a sample for this exact date
        cache_key = f"{symbol}_{date.strftime('%Y-%m-%d')}"
        if cache_key in self.news_samples:
            return False, "exact_match_cached"
        
        # Apply sampling strategy
        if self.sampling_strategy == 'daily':
            return True, "daily_strategy"
            
        elif self.sampling_strategy == 'weekly':
            # Monday only (or first trading day of week)
            if date.weekday() == 0:
                return True, "weekly_monday"
            return False, "weekly_skip"
            
        elif self.sampling_strategy == 'bi_weekly':
            # First and third Monday of month
            if date.weekday() == 0:
                week_of_month = (date.day - 1) // 7 + 1
                if week_of_month in [1, 3]:
                    return True, "bi_weekly_first_third"
            return False, "bi_weekly_skip"
            
        elif self.sampling_strategy == 'monthly':
            # First Monday of each month
            if date.weekday() == 0 and date.day <= 7:
                return True, "monthly_first_monday"
            return False, "monthly_skip"
            
        elif self.sampling_strategy == 'smart':
            return self._smart_sampling_decision(date, symbol, volatility_level)
            
        else:
            logger.warning(f"Unknown sampling strategy: {self.sampling_strategy}, defaulting to weekly")
            return self.should_fetch_news(date, symbol, volatility_level) if self.sampling_strategy == 'weekly' else (False, "unknown_strategy")
    
    def _smart_sampling_decision(self, date: datetime, symbol: str, volatility_level: float = None) -> Tuple[bool, str]:
        """Smart adaptive sampling based on market conditions."""
        
        # Base sampling: weekly
        is_monday = date.weekday() == 0
        
        # Increase frequency during high volatility
        if volatility_level is not None:
            if volatility_level > 40:  # High VXX
                # Sample every trading day during high volatility
                if date.weekday() < 5:  # Monday-Friday
                    return True, "smart_high_volatility"
            elif volatility_level > 30:  # Moderate VXX  
                # Sample twice per week during moderate volatility
                if date.weekday() in [0, 3]:  # Monday and Thursday
                    return True, "smart_moderate_volatility"
        
        # Default to weekly for normal conditions
        if is_monday:
            return True, "smart_weekly_default"
            
        return False, "smart_skip"
    
    def get_news_for_date(self, date: datetime, symbol: str, 
                         fetch_function, volatility_level: float = None) -> Tuple[pd.DataFrame, str]:
        """
        Get news for specified date - either fresh fetch or intelligent cache reuse.
        
        Args:
            date: Target date
            symbol: Stock symbol
            fetch_function: Function to call for fresh news fetch
            volatility_level: Optional VXX level for smart sampling
            
        Returns:
            (news_data: pd.DataFrame, source: str)  # source: 'fresh', 'exact_cache', 'interpolated_cache'
        """
        should_fetch, reason = self.should_fetch_news(date, symbol, volatility_level)
        
        if should_fetch:
            # Fetch fresh news
            try:
                logger.debug(f"📰 Fetching fresh news for {symbol} on {date.strftime('%Y-%m-%d')} ({reason})")
                news_data = fetch_function(symbol, date.strftime('%Y-%m-%d'), date.strftime('%Y-%m-%d'))
                
                # Cache the result
                sample = NewsSample(
                    date=date,
                    symbol=symbol,
                    news_data=news_data,
                    cache_key=f"{symbol}_{date.strftime('%Y-%m-%d')}",
                    fetch_timestamp=datetime.now(),
                    sampling_reason=reason
                )
                
                self.news_samples[sample.cache_key] = sample
                self._save_sample(sample)
                self.api_calls_made += 1
                
                logger.info(f"📰 Fresh news fetched: {len(news_data)} articles ({self.api_calls_made}/{self.max_calls_per_test} calls)")
                return news_data, "fresh"
                
            except Exception as e:
                logger.error(f"❌ Error fetching news for {symbol} on {date}: {e}")
                # Fall back to cached data
                return self._get_cached_news(date, symbol), "error_fallback"
        
        else:
            # Use cached data (unless strict sampling mode)
            if self.strict_sampling:
                logger.debug(f"📰 Strict sampling: no data for {symbol} on {date.strftime('%Y-%m-%d')} ({reason})")
                return pd.DataFrame(), f"strict_{reason}"
            
            self.cache_hits += 1
            cached_news = self._get_cached_news(date, symbol)
            logger.debug(f"📰 Using cached news for {symbol} on {date.strftime('%Y-%m-%d')} ({reason})")
            return cached_news, f"cached_{reason}"
    
    def _get_cached_news(self, date: datetime, symbol: str) -> pd.DataFrame:
        """Get cached news data, using intelligent interpolation if needed."""
        
        # Look for exact match first
        exact_key = f"{symbol}_{date.strftime('%Y-%m-%d')}"
        if exact_key in self.news_samples:
            return self.news_samples[exact_key].news_data
        
        # Find nearest cached samples
        symbol_samples = [
            sample for sample in self.news_samples.values()
            if sample.symbol == symbol
        ]
        
        if not symbol_samples:
            logger.warning(f"📰 No cached news found for {symbol}, returning empty DataFrame")
            return pd.DataFrame()
        
        # Find closest sample by date
        closest_sample = min(
            symbol_samples,
            key=lambda s: abs((s.date - date).days)
        )
        
        days_diff = abs((closest_sample.date - date).days)
        
        if days_diff <= self.cache_window_days:  # Use news within configured window
            logger.debug(f"📰 Using cached news from {closest_sample.date.strftime('%Y-%m-%d')} ({days_diff} days ago)")
            return closest_sample.news_data
        else:
            logger.warning(f"📰 Cached news too old ({days_diff} days > {self.cache_window_days}d window), returning empty DataFrame")
            return pd.DataFrame()
    
    def _load_existing_samples(self):
        """Load existing news samples from cache."""
        
        samples_file = self.cache_dir / "news_samples.json"
        if not samples_file.exists():
            return
        
        try:
            with open(samples_file, 'r') as f:
                samples_data = json.load(f)
            
            for cache_key, sample_data in samples_data.items():
                # Reconstruct NewsSample from cached data
                sample = NewsSample(
                    date=datetime.fromisoformat(sample_data['date']),
                    symbol=sample_data['symbol'],
                    news_data=pd.DataFrame(sample_data['news_data']),
                    cache_key=cache_key,
                    fetch_timestamp=datetime.fromisoformat(sample_data['fetch_timestamp']),
                    sampling_reason=sample_data['sampling_reason']
                )
                
                self.news_samples[cache_key] = sample
            
            logger.info(f"📰 Loaded {len(self.news_samples)} cached news samples")
            
        except Exception as e:
            logger.warning(f"⚠️ Error loading news samples cache: {e}")
    
    def _save_sample(self, sample: NewsSample):
        """Save a news sample to cache."""
        
        samples_file = self.cache_dir / "news_samples.json"
        
        # Load existing samples
        samples_data = {}
        if samples_file.exists():
            try:
                with open(samples_file, 'r') as f:
                    samples_data = json.load(f)
            except:
                pass
        
        # Add new sample
        samples_data[sample.cache_key] = {
            'date': sample.date.isoformat(),
            'symbol': sample.symbol,
            'news_data': sample.news_data.to_dict('records') if not sample.news_data.empty else [],
            'fetch_timestamp': sample.fetch_timestamp.isoformat(),
            'sampling_reason': sample.sampling_reason
        }
        
        # Save updated samples
        try:
            with open(samples_file, 'w') as f:
                json.dump(samples_data, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Error saving news sample cache: {e}")
    
    def get_quota_status(self) -> Dict[str, any]:
        """Get current quota usage and efficiency metrics."""
        
        total_requests = self.api_calls_made + self.cache_hits
        cache_hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'api_calls_made': self.api_calls_made,
            'cache_hits': self.cache_hits,
            'total_requests': total_requests,
            'cache_hit_rate_pct': round(cache_hit_rate, 1),
            'quota_remaining': self.max_calls_per_test - self.api_calls_made,
            'quota_usage_pct': round(self.api_calls_made / self.max_calls_per_test * 100, 1),
            'efficiency_rating': self._calculate_efficiency_rating(cache_hit_rate)
        }
    
    def _calculate_efficiency_rating(self, cache_hit_rate: float) -> str:
        """Calculate efficiency rating based on cache performance."""
        
        if cache_hit_rate >= 80:
            return "🟢 Excellent"
        elif cache_hit_rate >= 60:
            return "🟡 Good"  
        elif cache_hit_rate >= 40:
            return "🟠 Fair"
        else:
            return "🔴 Poor"
    
    def print_quota_summary(self):
        """Print a summary of quota usage and efficiency."""
        
        status = self.get_quota_status()
        
        print(f"\n📊 NEWS GOVERNOR QUOTA SUMMARY")
        print(f"{'='*50}")
        print(f"Strategy: {self.sampling_strategy}")
        print(f"API Calls Made: {status['api_calls_made']}/{self.max_calls_per_test} ({status['quota_usage_pct']}%)")
        print(f"Cache Hits: {status['cache_hits']}")
        print(f"Cache Hit Rate: {status['cache_hit_rate_pct']}%")
        print(f"Efficiency: {status['efficiency_rating']}")
        print(f"Quota Remaining: {status['quota_remaining']}")
        
        # Recommendations
        if status['quota_usage_pct'] > 90:
            print(f"⚠️  Warning: High quota usage, consider reducing sampling frequency")
        elif status['cache_hit_rate_pct'] < 50:
            print(f"💡 Tip: Low cache hit rate, consider weekly or bi-weekly sampling")
        elif status['efficiency_rating'] == "🟢 Excellent":
            print(f"✅ Optimal efficiency achieved!")


def create_conservative_governor(max_calls: int = 30) -> NewsGovernor:
    """Create a conservative news governor (1-2 day cache window, weekly sampling)."""
    return NewsGovernor(
        sampling_strategy='weekly',
        max_calls_per_test=max_calls,
        cache_window_days=2,  # Only use news within 1-2 days
        strict_sampling=False
    )

def create_balanced_governor(max_calls: int = 50) -> NewsGovernor:
    """Create a balanced news governor (1 week cache window, weekly sampling)."""
    return NewsGovernor(
        sampling_strategy='weekly',
        max_calls_per_test=max_calls,
        cache_window_days=7,  # Use news within a week
        strict_sampling=False
    )

def create_aggressive_governor(max_calls: int = 20) -> NewsGovernor:
    """Create an aggressive news governor (2 week cache window, bi-weekly sampling)."""
    return NewsGovernor(
        sampling_strategy='bi_weekly',
        max_calls_per_test=max_calls,
        cache_window_days=14,  # Use news within 2 weeks
        strict_sampling=False
    )

def create_strict_governor(max_calls: int = 15) -> NewsGovernor:
    """Create a strict news governor (no cache reuse, only sampling days get news)."""
    return NewsGovernor(
        sampling_strategy='weekly',
        max_calls_per_test=max_calls,
        cache_window_days=0,  # No cache reuse
        strict_sampling=True  # Only fetch on sampling days
    )

def get_recommended_sampling_strategy(test_duration_days: int, 
                                    target_api_calls: int = 50) -> str:
    """
    Recommend optimal sampling strategy based on test parameters.
    
    Args:
        test_duration_days: Number of days in test period
        target_api_calls: Target number of API calls
        
    Returns:
        Recommended sampling strategy
    """
    
    # Estimate trading days (roughly 70% of calendar days)
    trading_days = int(test_duration_days * 0.7)
    
    if target_api_calls >= trading_days:
        return 'daily'
    elif target_api_calls >= trading_days // 5:  # Weekly sampling
        return 'weekly'
    elif target_api_calls >= trading_days // 10:  # Bi-weekly sampling  
        return 'bi_weekly'
    else:
        return 'monthly'


# Example usage and testing
if __name__ == "__main__":
    # Test the news governor
    governor = NewsGovernor(sampling_strategy='weekly', max_calls_per_test=30)
    
    # Simulate test dates
    test_dates = pd.date_range('2024-01-01', '2024-03-31', freq='D')
    
    def mock_fetch_function(symbol, start_date, end_date):
        """Mock news fetch function for testing."""
        return pd.DataFrame({
            'title': [f"News for {symbol} on {start_date}"],
            'summary': [f"Mock news summary for {symbol}"],
            'url': [f"https://example.com/news/{symbol}"],
            'published_date': [start_date],
            'source': ['Mock Source']
        })
    
    # Test sampling
    for date in test_dates:
        if date.weekday() < 5:  # Trading days only
            news_data, source = governor.get_news_for_date(
                date, 'AAPL', mock_fetch_function
            )
            
    # Print summary
    governor.print_quota_summary()