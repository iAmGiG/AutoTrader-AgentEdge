import unittest
import sys
import os
from datetime import datetime, timedelta

# Add src to Python path so imports work
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from src.tools.date_utils import (
    get_default_date_range,
    process_date_param,
    get_processed_date_range,
    align_interval,
)
from src.tools.agent_utils import QueryParser
import pandas as pd


class TestDateUtils(unittest.TestCase):

    def test_get_default_date_range(self):
        """Test default date range generation"""
        start_date, end_date = get_default_date_range(days_back=5)

        # Check that end date is today
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(end_date, today)

        # Check that start date is approximately 7 calendar days before today (for 5 trading days)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        delta = end_dt - start_dt

        # The function uses 1.4 as multiplier to approximate trading days
        # So 5 trading days should be about 7 calendar days
        # Allow some flexibility in the test
        self.assertTrue(6 <= delta.days <= 8)

    def test_process_date_param(self):
        """Test date parameter processing"""
        # Test with explicit date
        self.assertEqual(
            process_date_param("2023-01-01"),
            "2023-01-01"
        )

        # Test with None
        self.assertIsNone(process_date_param(None))

        # Test with today
        today = datetime.now().strftime("%Y-%m-%d")
        self.assertEqual(process_date_param("today"), today)

        # Test with yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(process_date_param("yesterday"), yesterday)

        # Test with relative days
        days_ago_7 = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        self.assertEqual(process_date_param("-7d"), days_ago_7)

        # Test with relative weeks
        weeks_ago_2 = (datetime.now() - timedelta(weeks=2)
                       ).strftime("%Y-%m-%d")
        self.assertEqual(process_date_param("-2w"), weeks_ago_2)

        # Test with year to date
        ytd = datetime(datetime.now().year, 1, 1).strftime("%Y-%m-%d")
        self.assertEqual(process_date_param("ytd"), ytd)

        # Test with invalid format
        self.assertIsNone(process_date_param("invalid-date"))

    def test_get_processed_date_range(self):
        """Test the date range processing logic"""
        # Test with explicit dates
        start, end = get_processed_date_range("2023-01-01", "2023-02-01")
        self.assertEqual(start, "2023-01-01")
        self.assertEqual(end, "2023-02-01")

        # Test with only start date
        start, end = get_processed_date_range("2023-01-01", None)
        self.assertEqual(start, "2023-01-01")
        self.assertEqual(end, datetime.now().strftime("%Y-%m-%d"))

        # Test with only end date
        today = datetime.now()
        end_date = today.strftime("%Y-%m-%d")
        start, end = get_processed_date_range(None, end_date)
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        delta = end_dt - start_dt
        # Should be about 7 calendar days
        self.assertTrue(6 <= delta.days <= 8)

        # Test with no dates
        start, end = get_processed_date_range(None, None)
        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")
        delta = end_dt - start_dt
        # Should be about 7 calendar days
        self.assertTrue(6 <= delta.days <= 8)

        # Test with relative dates
        days_ago_30 = (datetime.now() - timedelta(days=30)
                       ).strftime("%Y-%m-%d")
        start, end = get_processed_date_range("-30d", "today")
        self.assertEqual(start, days_ago_30)
        self.assertEqual(end, datetime.now().strftime("%Y-%m-%d"))

    def test_validate_interval_lookback_invalid(self):
        with self.assertRaises(ValueError):
            QueryParser.validate_interval_lookback("1m", "180d")

    def test_validate_interval_lookback_valid(self):
        QueryParser.validate_interval_lookback("1m", "60d")

    def test_align_interval_downsample(self):
        rng = pd.date_range("2024-01-01", periods=120, freq="T")
        df = pd.DataFrame(
            {
                "Open": range(120),
                "High": range(120),
                "Low": range(120),
                "Close": range(120),
                "Volume": [1] * 120,
            },
            index=rng,
        )
        res = align_interval(df, "1h")
        self.assertEqual(len(res), 2)

    def test_align_interval_upsample(self):
        rng = pd.date_range("2024-01-01", periods=2, freq="H")
        df = pd.DataFrame({"Close": [1, 2]}, index=rng)
        res = align_interval(df, "30m")
        self.assertEqual(len(res), 3)


if __name__ == '__main__':
    unittest.main()
