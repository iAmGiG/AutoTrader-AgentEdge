"""
Google Search API Quota Manager
Prevents going over the free tier limit of 100 searches per day
"""

import json
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class GoogleSearchQuotaManager:
    """Manages Google Search API quota to prevent exceeding free tier limits"""

    def __init__(self, quota_file: str = "./.cache/google_search_quota.json"):
        self.quota_file = quota_file
        self.daily_limit = 100  # Free tier limit
        self.safety_buffer = 10  # Keep 10 searches as buffer
        self.usable_limit = self.daily_limit - self.safety_buffer

        # Ensure directory exists
        os.makedirs(os.path.dirname(quota_file), exist_ok=True)

        # Load existing quota data
        self.quota_data = self._load_quota_data()

    def _load_quota_data(self) -> dict:
        """Load quota tracking data from file"""
        if os.path.exists(self.quota_file):
            try:
                with open(self.quota_file, 'r') as f:
                    data = json.load(f)
                return data
            except Exception as e:
                logger.error(f"Error loading quota data: {e}")

        # Default quota data structure
        return {
            'daily_usage': {},
            'total_usage': 0,
            'last_reset': datetime.now().isoformat()
        }

    def _save_quota_data(self):
        """Save quota tracking data to file"""
        try:
            with open(self.quota_file, 'w') as f:
                json.dump(self.quota_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving quota data: {e}")

    def _get_today_key(self) -> str:
        """Get today's date key for tracking"""
        return datetime.now().strftime('%Y-%m-%d')

    def _cleanup_old_data(self):
        """Remove quota data older than 7 days"""
        cutoff_date = datetime.now() - timedelta(days=7)
        today_key = self._get_today_key()

        # Clean up old daily usage data
        old_keys = []
        for date_key in self.quota_data['daily_usage'].keys():
            try:
                date_obj = datetime.strptime(date_key, '%Y-%m-%d')
                if date_obj < cutoff_date:
                    old_keys.append(date_key)
            except:
                old_keys.append(date_key)  # Remove invalid keys

        for old_key in old_keys:
            del self.quota_data['daily_usage'][old_key]

    def get_today_usage(self) -> int:
        """Get number of searches used today"""
        today_key = self._get_today_key()
        return self.quota_data['daily_usage'].get(today_key, 0)

    def get_remaining_quota(self) -> int:
        """Get remaining searches available today"""
        used_today = self.get_today_usage()
        return max(0, self.usable_limit - used_today)

    def can_make_search(self, num_searches: int = 1) -> bool:
        """Check if we can make N searches without exceeding quota"""
        remaining = self.get_remaining_quota()
        return remaining >= num_searches

    def record_search(self, num_searches: int = 1) -> bool:
        """Record that N searches were made. Returns True if successful."""
        if not self.can_make_search(num_searches):
            logger.warning(f"Cannot record {num_searches} searches - would exceed quota")
            return False

        today_key = self._get_today_key()

        # Update daily usage
        current_usage = self.quota_data['daily_usage'].get(today_key, 0)
        self.quota_data['daily_usage'][today_key] = current_usage + num_searches

        # Update total usage
        self.quota_data['total_usage'] += num_searches

        # Update last activity
        self.quota_data['last_reset'] = datetime.now().isoformat()

        # Clean up old data
        self._cleanup_old_data()

        # Save to file
        self._save_quota_data()

        logger.info(
            f"Recorded {num_searches} Google searches. Today: {self.get_today_usage()}/{self.usable_limit}")

        return True

    def get_quota_status(self) -> dict:
        """Get detailed quota status"""
        today_usage = self.get_today_usage()
        remaining = self.get_remaining_quota()

        return {
            'date': self._get_today_key(),
            'daily_limit': self.daily_limit,
            'safety_buffer': self.safety_buffer,
            'usable_limit': self.usable_limit,
            'used_today': today_usage,
            'remaining_today': remaining,
            'percentage_used': today_usage / self.usable_limit * 100 if self.usable_limit > 0 else 0,
            'total_usage': self.quota_data['total_usage'],
            'can_search': remaining > 0
        }

    def estimate_searches_for_plan(self, tickers: list, date_ranges: list) -> dict:
        """Estimate how many searches a plan would require"""
        total_searches = len(tickers) * len(date_ranges)

        remaining = self.get_remaining_quota()
        can_complete_today = total_searches <= remaining

        if not can_complete_today:
            days_needed = (total_searches / self.usable_limit)
            estimated_completion = datetime.now() + timedelta(days=days_needed)
        else:
            days_needed = 0
            estimated_completion = datetime.now()

        return {
            'total_searches_needed': total_searches,
            'can_complete_today': can_complete_today,
            'remaining_today': remaining,
            'days_needed': days_needed,
            'estimated_completion': estimated_completion.strftime('%Y-%m-%d'),
            'searches_per_day': self.usable_limit
        }

    def get_safe_batch_size(self) -> int:
        """Get safe number of searches we can make right now"""
        remaining = self.get_remaining_quota()

        # Conservative batching - don't use all remaining quota at once
        if remaining > 20:
            return min(10, remaining - 5)  # Leave some buffer
        elif remaining > 10:
            return min(5, remaining - 2)   # Smaller batches when low
        elif remaining > 0:
            return min(2, remaining)       # Very conservative when almost out
        else:
            return 0

    def reset_daily_quota(self):
        """Manual reset for testing purposes (don't use in production)"""
        today_key = self._get_today_key()
        if today_key in self.quota_data['daily_usage']:
            del self.quota_data['daily_usage'][today_key]
        self._save_quota_data()
        logger.warning("Manually reset daily quota - this should only be used for testing!")


# Global quota manager instance
_quota_manager = None


def get_quota_manager() -> GoogleSearchQuotaManager:
    """Get global quota manager instance"""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = GoogleSearchQuotaManager()
    return _quota_manager


def check_quota_before_search(num_searches: int = 1) -> bool:
    """Convenience function to check quota before making searches"""
    manager = get_quota_manager()
    return manager.can_make_search(num_searches)


def record_search_usage(num_searches: int = 1) -> bool:
    """Convenience function to record search usage"""
    manager = get_quota_manager()
    return manager.record_search(num_searches)


def get_current_quota_status() -> dict:
    """Convenience function to get current quota status"""
    manager = get_quota_manager()
    return manager.get_quota_status()
