"""
Google Search Batch Manager
Manages batch operations while respecting quota limits
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from .google_search_quota_manager import get_quota_manager
from ..sources.api_based.google_search_news_tool import search_google_historical_news

logger = logging.getLogger(__name__)


class GoogleSearchBatchManager:
    """Manages batch searches while respecting quota limits"""

    def __init__(self):
        self.quota_manager = get_quota_manager()

    def plan_historical_cache_build(self,
                                    tickers: List[str],
                                    date_ranges: List[Tuple[str, str]],
                                    articles_per_search: int = 10) -> Dict:
        """Plan a historical cache building operation"""

        total_searches = len(tickers) * len(date_ranges)
        quota_status = self.quota_manager.get_quota_status()

        plan = {
            'total_searches_needed': total_searches,
            'articles_per_search': articles_per_search,
            'estimated_total_articles': total_searches * articles_per_search,
            'quota_status': quota_status,
            'can_complete_today': quota_status['remaining_today'] >= total_searches,
            'safe_batch_size': self.quota_manager.get_safe_batch_size(),
            'execution_plan': []
        }

        # Create execution batches
        remaining_searches = total_searches
        remaining_quota = quota_status['remaining_today']
        current_date = datetime.now()

        while remaining_searches > 0:
            if remaining_quota > 0:
                batch_size = min(remaining_searches, remaining_quota,
                                 self.quota_manager.get_safe_batch_size())

                plan['execution_plan'].append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'batch_size': batch_size,
                    'cumulative_searches': total_searches - remaining_searches + batch_size,
                    'quota_after': remaining_quota - batch_size
                })

                remaining_searches -= batch_size
                remaining_quota -= batch_size
            else:
                # Move to next day
                current_date += timedelta(days=1)
                remaining_quota = self.quota_manager.usable_limit

        return plan

    def execute_safe_batch(self,
                           searches: List[Dict],
                           max_batch_size: int = None) -> List[Dict]:
        """Execute a batch of searches safely within quota limits"""

        if max_batch_size is None:
            max_batch_size = self.quota_manager.get_safe_batch_size()

        results = []
        executed_count = 0

        logger.info(
            f"Starting safe batch execution: {len(searches)} planned, max batch size: {max_batch_size}")

        for search_spec in searches[:max_batch_size]:
            # Check quota before each search
            if not self.quota_manager.can_make_search(1):
                logger.warning(f"Quota exhausted after {executed_count} searches. Stopping batch.")
                break

            try:
                ticker = search_spec['ticker']
                start_date = search_spec['start_date']
                end_date = search_spec['end_date']
                max_results = search_spec.get('max_results', 10)

                logger.info(
                    f"Executing search {executed_count + 1}: {ticker} {start_date}-{end_date}")

                df = search_google_historical_news(
                    ticker=ticker,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_results
                )

                result = {
                    'ticker': ticker,
                    'start_date': start_date,
                    'end_date': end_date,
                    'articles_found': len(df),
                    'success': not df.empty,
                    'search_spec': search_spec
                }

                if not df.empty:
                    result['sample_headlines'] = df['title'].head(3).tolist()
                    result['sources'] = df['source'].unique().tolist()

                results.append(result)
                executed_count += 1

                # Small delay between searches to be respectful
                import time
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Error in search {executed_count + 1}: {e}")
                results.append({
                    'ticker': search_spec['ticker'],
                    'start_date': search_spec['start_date'],
                    'end_date': search_spec['end_date'],
                    'articles_found': 0,
                    'success': False,
                    'error': str(e),
                    'search_spec': search_spec
                })

        quota_status = self.quota_manager.get_quota_status()
        logger.info(
            f"Batch complete: {executed_count} searches executed. Quota remaining: {quota_status['remaining_today']}")

        return results

    def build_october_2022_cache(self,
                                 tickers: List[str] = None,
                                 safe_mode: bool = True) -> Dict:
        """Build cache for October 2022 MAG7 data"""

        if tickers is None:
            tickers = ['TSLA', 'AAPL', 'NVDA']  # Start with most volatile/news-heavy

        # Define October 2022 date ranges
        date_ranges = [
            ('2022-10-01', '2022-10-15'),  # Early October
            ('2022-10-16', '2022-10-31'),  # Late October
        ]

        # Build search specifications
        searches = []
        for ticker in tickers:
            for start_date, end_date in date_ranges:
                searches.append({
                    'ticker': ticker,
                    'start_date': start_date,
                    'end_date': end_date,
                    'max_results': 10
                })

        # Create execution plan
        plan = self.plan_historical_cache_build(tickers, date_ranges)

        logger.info(f"October 2022 cache build plan:")
        logger.info(f"  Tickers: {tickers}")
        logger.info(f"  Total searches: {plan['total_searches_needed']}")
        logger.info(f"  Can complete today: {plan['can_complete_today']}")
        logger.info(f"  Safe batch size: {plan['safe_batch_size']}")

        if safe_mode:
            # Execute only safe batch size
            max_batch = plan['safe_batch_size']
            logger.info(f"Safe mode: executing maximum {max_batch} searches")
        else:
            # Execute all remaining quota
            max_batch = plan['quota_status']['remaining_today']
            logger.info(f"Full mode: executing up to {max_batch} searches")

        # Execute the batch
        results = self.execute_safe_batch(searches, max_batch)

        # Summarize results
        successful_searches = sum(1 for r in results if r['success'])
        total_articles = sum(r['articles_found'] for r in results)

        summary = {
            'execution_plan': plan,
            'results': results,
            'summary': {
                'searches_executed': len(results),
                'searches_successful': successful_searches,
                'total_articles_cached': total_articles,
                'quota_remaining': self.quota_manager.get_quota_status()['remaining_today']
            }
        }

        return summary

    def get_quota_report(self) -> Dict:
        """Get detailed quota usage report"""
        quota_status = self.quota_manager.get_quota_status()

        # Calculate cost if we exceeded free tier
        used_today = quota_status['used_today']
        free_limit = quota_status['usable_limit']

        if used_today > free_limit:
            overage = used_today - free_limit
            cost_estimate = overage * 0.005  # $5 per 1000 searches
        else:
            overage = 0
            cost_estimate = 0.0

        report = {
            'quota_status': quota_status,
            'overage_searches': overage,
            'estimated_cost': cost_estimate,
            'recommendations': []
        }

        # Add recommendations
        if quota_status['percentage_used'] > 90:
            report['recommendations'].append(
                "⚠️  Near quota limit - be very careful with additional searches")
        elif quota_status['percentage_used'] > 70:
            report['recommendations'].append("🔍 Moderate usage - consider smaller batch sizes")
        elif quota_status['percentage_used'] > 50:
            report['recommendations'].append("✅ Good usage level - can continue normal operations")
        else:
            report['recommendations'].append("💚 Low usage - plenty of quota remaining")

        if overage > 0:
            report['recommendations'].append(
                f"💰 COST ALERT: Exceeded free tier by {overage} searches (~${cost_estimate:.2f})")

        return report


def quick_october_2022_build(safe_mode: bool = True) -> Dict:
    """Quick function to start building October 2022 cache"""
    manager = GoogleSearchBatchManager()
    return manager.build_october_2022_cache(safe_mode=safe_mode)


def check_quota_status() -> Dict:
    """Quick function to check quota status"""
    manager = GoogleSearchBatchManager()
    return manager.get_quota_report()
