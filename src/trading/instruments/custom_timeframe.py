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

    original: str  # Original input (e.g., "65m", "1.5h", "2d", "30s")
    type: str  # "native", "custom_minute", "fractional_hour", "multi_day", "multi_week"
    value: float  # Numeric value (minutes, days, weeks depending on type)
    minutes: int  # Total minutes for aggregation
    is_native: bool  # True if API supports directly
    warnings: list = None  # List of warning messages (displayed with * indicator)
    effective: str = None  # What timeframe is actually used (if different from original)

    def __post_init__(self):
        """Initialize defaults after creation."""
        if self.warnings is None:
            self.warnings = []
        if self.effective is None:
            self.effective = self.original

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def get_display_label(self) -> str:
        """
        Get display label with * indicator if warnings exist.

        Returns:
            str: Timeframe label, e.g., "65m*" if custom, "1m*" if converted from seconds
        """
        label = self.effective
        # Add * for custom (non-native) timeframes
        if not self.is_native or self.has_warnings():
            return f"{label}*"
        return label

    def get_warning_summary(self) -> str:
        """Get formatted warning messages."""
        if not self.warnings:
            return ""
        return " | ".join(self.warnings)


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
    def _parse_seconds(timeframe_str: str) -> Optional[TimeframeSpec]:
        """Parse seconds notation (e.g., '30s') - converts to 1m with warning."""
        match = re.match(r"^(\d+)s$", timeframe_str)
        if not match:
            return None
        seconds = int(match.group(1))
        logger.warning(
            f"Sub-minute timeframe '{timeframe_str}' not supported by API. Defaulting to 1m."
        )
        return TimeframeSpec(
            original=timeframe_str,
            type="native",
            value=1,
            minutes=1,
            is_native=True,
            warnings=[f"Sub-minute ({seconds}s) not available, using 1m"],
            effective="1m",
        )

    @staticmethod
    def _parse_native(timeframe_str: str) -> Optional[TimeframeSpec]:
        """Parse native API-supported timeframes."""
        native_lower = {tf.lower(): tf for tf in TimeframeParser.NATIVE_TIMEFRAMES}
        if timeframe_str not in native_lower:
            return None
        original_tf = native_lower[timeframe_str]
        minutes = TimeframeParser._to_minutes_native(original_tf)
        return TimeframeSpec(
            original=timeframe_str,
            type="native",
            value=int(re.match(r"^(\d+)", original_tf).group(1)),
            minutes=minutes,
            is_native=True,
        )

    @staticmethod
    def _parse_custom_minute(timeframe_str: str) -> Optional[TimeframeSpec]:
        """Parse custom minute intervals (e.g., '65m', '89m')."""
        match = re.match(r"^(\d+)m$", timeframe_str)
        if not match:
            return None
        minutes = int(match.group(1))
        if not (1 <= minutes <= 1440):
            return None
        return TimeframeSpec(
            original=timeframe_str,
            type="custom_minute",
            value=minutes,
            minutes=minutes,
            is_native=False,
        )

    @staticmethod
    def _parse_fractional_hour(timeframe_str: str) -> Optional[TimeframeSpec]:
        """Parse fractional hours (e.g., '1.5h', '2.5h')."""
        match = re.match(r"^(\d+(?:\.\d+)?)h$", timeframe_str)
        if not match:
            return None
        hours = float(match.group(1))
        minutes = int(hours * 60)
        if not (60 <= minutes <= 1440):
            return None
        return TimeframeSpec(
            original=timeframe_str,
            type="fractional_hour",
            value=hours,
            minutes=minutes,
            is_native=False,
        )

    @staticmethod
    def _parse_multi_day(timeframe_str: str) -> Optional[TimeframeSpec]:
        """Parse multi-day bars (e.g., '2d', '3d')."""
        match = re.match(r"^(\d+)d$", timeframe_str)
        if not match:
            return None
        days = int(match.group(1))
        if not (1 <= days <= 365):
            return None
        return TimeframeSpec(
            original=timeframe_str,
            type="multi_day",
            value=days,
            minutes=days * 1440,
            is_native=False,
        )

    @staticmethod
    def _parse_multi_week(timeframe_str: str) -> Optional[TimeframeSpec]:
        """Parse multi-week bars (e.g., '2w', '4w')."""
        match = re.match(r"^(\d+)w$", timeframe_str)
        if not match:
            return None
        weeks = int(match.group(1))
        if not (1 <= weeks <= 52):
            return None
        return TimeframeSpec(
            original=timeframe_str,
            type="multi_week",
            value=weeks,
            minutes=weeks * 10080,
            is_native=False,
        )

    @staticmethod
    def parse(timeframe_str: str) -> Optional[TimeframeSpec]:
        """
        Parse timeframe notation into TimeframeSpec.

        Handles TradingView-style notation: 1m, 5m, 1h, 1d, 1w
        Also handles custom timeframes: 65m, 1.5h, 2d, 2w
        Sub-minute (seconds) notation is converted to 1m with warning.

        Args:
            timeframe_str: Timeframe notation (e.g., "65m", "1.5h", "2d", "30s")

        Returns:
            TimeframeSpec or None if invalid
        """
        timeframe_str = timeframe_str.strip().lower()

        # Try each parser in order of priority
        parsers = [
            TimeframeParser._parse_seconds,
            TimeframeParser._parse_native,
            TimeframeParser._parse_custom_minute,
            TimeframeParser._parse_fractional_hour,
            TimeframeParser._parse_multi_day,
            TimeframeParser._parse_multi_week,
        ]

        for parser in parsers:
            result = parser(timeframe_str)
            if result is not None:
                return result

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
        """Get information about a timeframe with warnings."""
        spec = self.parser.parse(timeframe)
        if not spec:
            return None

        return {
            "original": spec.original,
            "effective": spec.effective,
            "display": spec.get_display_label(),
            "type": spec.type,
            "is_native": spec.is_native,
            "value": spec.value,
            "minutes": spec.minutes,
            "has_warnings": spec.has_warnings(),
            "warnings": spec.warnings,
        }

    def check_data_sufficiency(
        self,
        symbol: str,
        timeframe: str,
        available_days: int,
    ) -> Dict:
        """
        Check if there's sufficient data for the requested timeframe.

        Args:
            symbol: Stock symbol
            timeframe: Target timeframe
            available_days: Number of days of data available for the symbol

        Returns:
            Dict with sufficiency status and warnings
        """
        spec = self.parser.parse(timeframe)
        if not spec:
            return {"sufficient": False, "warnings": ["Invalid timeframe"]}

        warnings = list(spec.warnings)  # Copy existing warnings
        sufficient = True

        # Calculate minimum required days based on timeframe type
        min_required_days = 1  # Default

        if spec.type == "multi_week":
            # For weekly bars, need at least 2x the bar size in weeks
            min_required_days = spec.value * 14  # 2 weeks * 7 days
        elif spec.type == "multi_day":
            # For multi-day bars, need at least 3x the bar size
            min_required_days = spec.value * 3
        elif spec.type in ("custom_minute", "fractional_hour"):
            # For intraday custom timeframes, need at least 3 trading days
            min_required_days = 3
        elif spec.type == "native":
            # Native timeframes need less data
            if "w" in spec.effective.lower():
                min_required_days = 14
            elif "d" in spec.effective.lower():
                min_required_days = 5
            else:
                min_required_days = 1

        if available_days < min_required_days:
            sufficient = False
            warnings.append(
                f"Insufficient history: {available_days}d available, "
                f"{min_required_days}d recommended for {timeframe}"
            )

        # Mark new/limited symbols
        if available_days < 30:
            warnings.append(f"Limited data: Only {available_days}d of history for {symbol}")

        return {
            "sufficient": sufficient,
            "available_days": available_days,
            "min_required_days": min_required_days,
            "warnings": warnings,
            "display_label": f"{spec.effective}*" if warnings else spec.effective,
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

    # Test parser including seconds and warning system
    test_frames = [
        "65m",  # Custom minute (non-native)
        "1.5h",  # Fractional hour
        "2d",  # Multi-day
        "2w",  # Multi-week
        "89m",  # Fibonacci custom
        "13m",  # Native Fibonacci
        "30s",  # Seconds (should convert to 1m with warning)
        "5s",  # Seconds (should convert to 1m with warning)
        "1m",  # Native minute
        "4h",  # Native hour
        "invalid",  # Invalid
    ]

    print("=" * 70)
    print("Timeframe Parser Test (with Warning System)")
    print("=" * 70)
    print(f"{'Input':<10} {'Display':<12} {'Type':<18} {'Native':<8} {'Warnings'}")
    print("-" * 70)

    for tf in test_frames:
        spec = builder.parser.parse(tf)
        if spec:
            display = spec.get_display_label()
            warnings = spec.get_warning_summary() or "-"
            print(f"  {tf:<10} {display:<12} {spec.type:<18} {str(spec.is_native):<8} {warnings}")
        else:
            print(f"  {tf:<10} {'INVALID':<12}")

    print()
    print("=" * 70)
    print("Data Sufficiency Check Test")
    print("=" * 70)

    # Test data sufficiency for different scenarios
    test_cases = [
        ("AAPL", "1d", 365),  # Plenty of data
        ("NVDA", "2w", 30),  # Limited data for weekly
        ("NEWIPO", "4h", 5),  # New symbol, very limited
        ("SPY", "65m", 100),  # Good data for custom minute
    ]

    for symbol, tf, days in test_cases:
        result = builder.check_data_sufficiency(symbol, tf, days)
        status = "OK" if result["sufficient"] else "WARN"
        print(f"  {symbol:8} @ {tf:6} ({days:3}d): [{status:4}] {result['display_label']}")
        if result["warnings"]:
            for warn in result["warnings"]:
                print(f"           * {warn}")
