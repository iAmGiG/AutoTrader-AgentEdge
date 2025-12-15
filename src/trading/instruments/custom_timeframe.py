#!/usr/bin/env python3
"""
CustomTimeframeBuilder - Build arbitrary timeframes beyond API limits

Issue #407: CustomTimeframeBuilder - Arbitrary timeframe support beyond API limits

Enables construction of custom timeframes from lower-resolution data:
- Arbitrary minute bars (17m, 21m, 65m, 89m, 144m, etc.)
- Fractional hours (1.5h, 2.5h, etc.)
- Multi-day bars (2d, 3d, etc.)
- Multi-week bars (2w, 4w, etc.)

Examples:
    65m = 65-minute bars (6 bars per trading day)
    1.5h = 90-minute bars (fractional hours)
    2d = 2-day bars
    2w = 2-week bars
"""

import logging
import re
from dataclasses import dataclass
from datetime import time
from typing import Dict, Optional

import pandas as pd

from src.trading.instruments.data_fetch import fetch_market_data
from src.trading.instruments.timeframe_tools import convert_to_alpaca_timeframe

logger = logging.getLogger(__name__)


@dataclass
class TimeframeSpec:
    """Parsed timeframe specification."""

    original: str  # Original input (e.g., "65m", "1.5h", "2d")
    type: str  # "native", "custom_minute", "fractional_hour", "multi_day", "multi_week"
    value: int  # Numeric value (minutes, days, weeks depending on type)
    minutes: int  # Total minutes for aggregation
    is_native: bool  # True if API supports directly


class TimeframeParser:
    """Parse and validate timeframe notation."""

    # Timeframes directly supported by Alpaca API
    NATIVE_TIMEFRAMES = {
        "1m",
        "2m",
        "3m",
        "5m",
        "8m",
        "13m",
        "15m",
        "21m",
        "30m",
        "34m",
        "45m",
        "55m",
        "1h",
        "2h",
        "3h",
        "4h",
        "5h",
        "8h",
        "13h",
        "1d",
        "1w",
        "1M",
    }

    @staticmethod
    def parse(timeframe_str: str) -> Optional[TimeframeSpec]:
        """
        Parse timeframe notation into TimeframeSpec.

        Args:
            timeframe_str: Timeframe notation (e.g., "65m", "1.5h", "2d", "13m")

        Returns:
            TimeframeSpec or None if invalid
        """
        timeframe_str = timeframe_str.strip()

        # Check if native (directly supported)
        if timeframe_str in TimeframeParser.NATIVE_TIMEFRAMES:
            # Get minutes equivalent
            minutes = TimeframeParser._to_minutes_native(timeframe_str)
            return TimeframeSpec(
                original=timeframe_str,
                type="native",
                value=int(timeframe_str[:-1]),  # Extract number
                minutes=minutes,
                is_native=True,
            )

        # Try to parse custom minute interval (e.g., "65m", "89m")
        match = re.match(r"^(\d+)m$", timeframe_str)
        if match:
            minutes = int(match.group(1))
            if 1 <= minutes <= 1440:  # Up to 24 hours
                return TimeframeSpec(
                    original=timeframe_str,
                    type="custom_minute",
                    value=minutes,
                    minutes=minutes,
                    is_native=False,
                )

        # Try to parse fractional hours (e.g., "1.5h", "2.5h")
        match = re.match(r"^(\d+(?:\.\d+)?)h$", timeframe_str)
        if match:
            hours = float(match.group(1))
            minutes = int(hours * 60)
            if 60 <= minutes <= 1440:
                return TimeframeSpec(
                    original=timeframe_str,
                    type="fractional_hour",
                    value=hours,
                    minutes=minutes,
                    is_native=False,
                )

        # Try to parse multi-day bars (e.g., "2d", "3d")
        match = re.match(r"^(\d+)d$", timeframe_str)
        if match:
            days = int(match.group(1))
            if 1 <= days <= 365:
                return TimeframeSpec(
                    original=timeframe_str,
                    type="multi_day",
                    value=days,
                    minutes=days * 1440,  # Store as minutes for reference
                    is_native=False,
                )

        # Try to parse multi-week bars (e.g., "2w", "4w")
        match = re.match(r"^(\d+)w$", timeframe_str)
        if match:
            weeks = int(match.group(1))
            if 1 <= weeks <= 52:
                return TimeframeSpec(
                    original=timeframe_str,
                    type="multi_week",
                    value=weeks,
                    minutes=weeks * 10080,  # 7 * 1440 minutes per week
                    is_native=False,
                )

        logger.warning(f"Invalid timeframe notation: {timeframe_str}")
        return None

    @staticmethod
    def _to_minutes_native(tf: str) -> int:
        """Convert native timeframe to minutes."""
        if "m" in tf and "M" not in tf:
            return int(tf[:-1])
        elif "h" in tf:
            return int(tf[:-1]) * 60
        elif "d" in tf:
            return int(tf[:-1]) * 1440
        elif "w" in tf:
            return int(tf[:-1]) * 10080
        elif "M" in tf:
            return int(tf[:-1]) * 43200  # Approximate
        return 0


class CustomTimeframeBuilder:
    """Build custom timeframes from lower-resolution data."""

    TRADING_DAY_START = time(9, 30)  # 9:30 AM
    TRADING_DAY_END = time(16, 0)  # 4:00 PM
    MINUTES_PER_TRADING_DAY = 390  # 9:30 AM to 4:00 PM

    def __init__(self, cache_enabled: bool = True):
        """
        Initialize CustomTimeframeBuilder.

        Args:
            cache_enabled: Use caching for market data
        """
        self.cache_enabled = cache_enabled
        self.parser = TimeframeParser()

    def build_custom_bars(
        self,
        symbol: str,
        custom_timeframe: str,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Build custom timeframe bars from available data.

        Args:
            symbol: Stock symbol
            custom_timeframe: Target timeframe (e.g., "65m", "1.5h", "2d")
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data at custom interval or None
        """
        spec = self.parser.parse(custom_timeframe)
        if not spec:
            logger.error(f"Invalid timeframe: {custom_timeframe}")
            return None

        logger.info(f"Building {custom_timeframe} bars for {symbol} ({spec.type})")

        try:
            if spec.is_native:
                # Use API directly for native timeframes
                alpaca_tf = convert_to_alpaca_timeframe(custom_timeframe)
                return fetch_market_data(symbol, start_date, end_date, timeframe=alpaca_tf)

            elif spec.type == "custom_minute":
                # Build from 1-minute bars
                return self._build_minute_bars(symbol, spec.value, start_date, end_date)

            elif spec.type == "fractional_hour":
                # Build from 1-minute bars (convert hours to minutes)
                return self._build_minute_bars(symbol, spec.minutes, start_date, end_date)

            elif spec.type == "multi_day":
                # Build from daily bars
                return self._build_multi_day_bars(symbol, spec.value, start_date, end_date)

            elif spec.type == "multi_week":
                # Build from weekly bars
                return self._build_multi_week_bars(symbol, spec.value, start_date, end_date)

        except Exception as e:
            logger.error(f"Failed to build {custom_timeframe} bars: {e}")

        return None

    def _build_minute_bars(
        self,
        symbol: str,
        bar_minutes: int,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Build N-minute bars from 1-minute source data.

        Args:
            symbol: Stock symbol
            bar_minutes: Target bar size in minutes
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with aggregated bars
        """
        logger.debug(f"Fetching 1-minute data for {symbol}...")
        minute_data = fetch_market_data(symbol, start_date, end_date, timeframe="1Min")

        if minute_data is None or minute_data.empty:
            logger.warning(f"No 1-minute data available for {symbol}")
            return None

        logger.debug(f"Aggregating to {bar_minutes}-minute bars...")

        # Ensure DatetimeIndex
        if not isinstance(minute_data.index, pd.DatetimeIndex):
            minute_data.index = pd.to_datetime(minute_data.index)

        # Group by trading day and aggregate within day
        aggregated_bars = []

        for date, day_data in minute_data.groupby(minute_data.index.date):
            # Only process trading hours (9:30 AM - 4:00 PM)
            day_data = day_data.between_time("09:30", "16:00")

            if day_data.empty:
                continue

            # Resample to target interval
            resampled = day_data.resample(f"{bar_minutes}min").agg(
                {
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum",
                }
            )

            # Drop incomplete bars at end of day
            resampled = resampled.dropna()
            aggregated_bars.append(resampled)

        if not aggregated_bars:
            logger.warning(f"No bars created for {symbol} at {bar_minutes}m interval")
            return None

        result = pd.concat(aggregated_bars)
        logger.info(f"Created {len(result)} bars for {symbol}")
        return result

    def _build_multi_day_bars(
        self,
        symbol: str,
        num_days: int,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Build N-day bars from daily data.

        Args:
            symbol: Stock symbol
            num_days: Number of days per bar
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with multi-day bars
        """
        logger.debug(f"Fetching daily data for {symbol}...")
        daily_data = fetch_market_data(symbol, start_date, end_date, timeframe="1Day")

        if daily_data is None or daily_data.empty:
            logger.warning(f"No daily data available for {symbol}")
            return None

        logger.debug(f"Aggregating to {num_days}-day bars...")

        # Resample to N-day intervals
        result = (
            daily_data.resample(f"{num_days}D")
            .agg(
                {
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum",
                }
            )
            .dropna()
        )

        logger.info(f"Created {len(result)} {num_days}-day bars for {symbol}")
        return result

    def _build_multi_week_bars(
        self,
        symbol: str,
        num_weeks: int,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Build N-week bars from weekly data.

        Args:
            symbol: Stock symbol
            num_weeks: Number of weeks per bar
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame with multi-week bars
        """
        logger.debug(f"Fetching weekly data for {symbol}...")
        weekly_data = fetch_market_data(symbol, start_date, end_date, timeframe="1Week")

        if weekly_data is None or weekly_data.empty:
            logger.warning(f"No weekly data available for {symbol}")
            return None

        logger.debug(f"Aggregating to {num_weeks}-week bars...")

        # Resample to N-week intervals
        result = (
            weekly_data.resample(f"{num_weeks}W")
            .agg(
                {
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum",
                }
            )
            .dropna()
        )

        logger.info(f"Created {len(result)} {num_weeks}-week bars for {symbol}")
        return result

    def validate_timeframe(self, timeframe: str) -> bool:
        """Check if timeframe notation is valid."""
        return self.parser.parse(timeframe) is not None

    def get_timeframe_info(self, timeframe: str) -> Optional[Dict]:
        """Get information about a timeframe."""
        spec = self.parser.parse(timeframe)
        if not spec:
            return None

        return {
            "original": spec.original,
            "type": spec.type,
            "is_native": spec.is_native,
            "value": spec.value,
            "minutes": spec.minutes,
        }


# Singleton instance
_builder: Optional[CustomTimeframeBuilder] = None


def get_custom_timeframe_builder() -> CustomTimeframeBuilder:
    """Get global CustomTimeframeBuilder instance."""
    global _builder
    if _builder is None:
        _builder = CustomTimeframeBuilder()
    return _builder


# Convenience functions
def build_custom_bars(
    symbol: str,
    custom_timeframe: str,
    start_date: str,
    end_date: str,
) -> Optional[pd.DataFrame]:
    """Convenience function to build custom timeframe bars."""
    return get_custom_timeframe_builder().build_custom_bars(
        symbol, custom_timeframe, start_date, end_date
    )


def validate_timeframe(timeframe: str) -> bool:
    """Check if timeframe is valid."""
    return get_custom_timeframe_builder().validate_timeframe(timeframe)


if __name__ == "__main__":
    # Quick test

    logging.basicConfig(level=logging.INFO)

    builder = get_custom_timeframe_builder()

    # Test parser
    test_frames = ["65m", "1.5h", "2d", "2w", "89m", "13m", "invalid"]
    print("=" * 60)
    print("Timeframe Parser Test")
    print("=" * 60)

    for tf in test_frames:
        spec = builder.parser.parse(tf)
        if spec:
            print(f"  {tf:10} -> {spec.type:20} (native={spec.is_native})")
        else:
            print(f"  {tf:10} -> INVALID")
