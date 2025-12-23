"""
Practical Trading Filters (#264)

Market condition filters that improve backtest realism by avoiding
trading during unfavorable conditions.

Filters Implemented:
- VolumeFilter: Skip abnormally low volume days
- GapFilter: Avoid excessive overnight gaps
- VIXFilter: Reduce sizing during high volatility
- EventFilter: Avoid FOMC, earnings, options expiry
- TimeFilter: Optimal trading hours

Usage:
    from src.backtesting.trading_filters import FilterManager

    filters = FilterManager()
    filters.add_filter(VolumeFilter(threshold=0.5))  # Skip <50% avg volume
    filters.add_filter(VIXFilter(threshold=30))     # Reduce sizing when VIX>30

    for date in trading_days:
        result = filters.apply(symbol, date, data)
        if result.skip:
            continue  # Don't trade this day
        position_size *= result.size_multiplier  # Adjust sizing
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


@dataclass
class FilterResult:
    """Result of applying a trading filter."""

    skip: bool = False  # Skip trading entirely
    size_multiplier: float = 1.0  # Adjust position size (0.0-1.0)
    reason: str = ""  # Human-readable reason
    filter_name: str = ""  # Name of filter that triggered
    data: Optional[Dict] = None  # Additional filter data


class TradingFilter(ABC):
    """Abstract base class for trading filters."""

    name: str = "base_filter"

    @abstractmethod
    def apply(
        self,
        symbol: str,
        date: str,
        data: pd.DataFrame,
        context: Optional[Dict] = None,
    ) -> FilterResult:
        """
        Apply filter to determine if trading should occur.

        Args:
            symbol: Ticker symbol
            date: Current date (YYYY-MM-DD)
            data: OHLCV data up to and including current date
            context: Optional additional context (VIX, events, etc.)

        Returns:
            FilterResult with skip flag and sizing adjustment
        """
        pass


class VolumeFilter(TradingFilter):
    """
    Skip trading on abnormally low volume days.

    Low volume can indicate:
    - Holiday-adjacent trading
    - Pre-market event positioning
    - Poor liquidity for execution
    """

    name = "volume_filter"

    def __init__(self, threshold: float = 0.5, lookback: int = 20):
        """
        Args:
            threshold: Volume must be >= this fraction of average (0.5 = 50%)
            lookback: Days for rolling average calculation
        """
        self.threshold = threshold
        self.lookback = lookback

    def apply(
        self,
        symbol: str,
        date: str,
        data: pd.DataFrame,
        context: Optional[Dict] = None,
    ) -> FilterResult:
        if len(data) < self.lookback + 1:
            return FilterResult()  # Not enough data, allow trading

        if "volume" not in data.columns:
            return FilterResult()  # No volume data, allow trading

        # Calculate rolling average volume (excluding current day)
        avg_volume = data["volume"].iloc[-self.lookback - 1 : -1].mean()
        current_volume = data["volume"].iloc[-1]

        if avg_volume == 0:
            return FilterResult()

        volume_ratio = current_volume / avg_volume

        if volume_ratio < self.threshold:
            return FilterResult(
                skip=True,
                reason=f"Volume {volume_ratio:.1%} of average (threshold: {self.threshold:.0%})",
                filter_name=self.name,
                data={"volume_ratio": volume_ratio, "avg_volume": avg_volume},
            )

        return FilterResult()


class GapFilter(TradingFilter):
    """
    Avoid trading on days with excessive overnight gaps.

    Large gaps can indicate:
    - After-hours news events
    - Earnings surprises
    - Market dislocations
    """

    name = "gap_filter"

    def __init__(self, threshold: float = 0.02):
        """
        Args:
            threshold: Maximum gap size as decimal (0.02 = 2%)
        """
        self.threshold = threshold

    def apply(
        self,
        symbol: str,
        date: str,
        data: pd.DataFrame,
        context: Optional[Dict] = None,
    ) -> FilterResult:
        if len(data) < 2:
            return FilterResult()

        if "open" not in data.columns or "close" not in data.columns:
            return FilterResult()

        # Gap = (today's open - yesterday's close) / yesterday's close
        prev_close = data["close"].iloc[-2]
        current_open = data["open"].iloc[-1]

        if prev_close == 0:
            return FilterResult()

        gap = (current_open - prev_close) / prev_close

        if abs(gap) > self.threshold:
            direction = "up" if gap > 0 else "down"
            return FilterResult(
                skip=True,
                reason=f"Gap {direction} {abs(gap):.1%} (threshold: {self.threshold:.0%})",
                filter_name=self.name,
                data={"gap": gap, "prev_close": prev_close, "current_open": current_open},
            )

        return FilterResult()


class VIXFilter(TradingFilter):
    """
    Reduce position sizing during high volatility periods.

    VIX thresholds:
    - VIX < 15: Normal conditions (full size)
    - VIX 15-20: Elevated volatility (80% size)
    - VIX 20-30: High volatility (60% size)
    - VIX > 30: Extreme volatility (40% size or skip)
    """

    name = "vix_filter"

    def __init__(self, threshold: float = 30, skip_above: Optional[float] = None):
        """
        Args:
            threshold: VIX level for position size reduction
            skip_above: VIX level to skip trading entirely (None = never skip)
        """
        self.threshold = threshold
        self.skip_above = skip_above

    def apply(
        self,
        symbol: str,
        date: str,
        data: pd.DataFrame,
        context: Optional[Dict] = None,
    ) -> FilterResult:
        # Get VIX from context
        vix = None
        if context and "vix" in context:
            vix = context["vix"]

        if vix is None:
            return FilterResult()

        # Skip entirely if VIX extremely high
        if self.skip_above and vix > self.skip_above:
            return FilterResult(
                skip=True,
                reason=f"VIX at {vix:.1f} exceeds skip threshold {self.skip_above}",
                filter_name=self.name,
                data={"vix": vix},
            )

        # Calculate size multiplier based on VIX level
        if vix > 30:
            multiplier = 0.4
        elif vix > 20:
            multiplier = 0.6
        elif vix > 15:
            multiplier = 0.8
        else:
            multiplier = 1.0

        if multiplier < 1.0:
            return FilterResult(
                skip=False,
                size_multiplier=multiplier,
                reason=f"VIX at {vix:.1f}, reducing position to {multiplier:.0%}",
                filter_name=self.name,
                data={"vix": vix, "multiplier": multiplier},
            )

        return FilterResult()


class EventFilter(TradingFilter):
    """
    Skip trading around major market events.

    Events tracked:
    - FOMC meetings (Fed rate decisions)
    - Options expiration (monthly OpEx, quad witching)
    - Market holidays (low liquidity)
    """

    name = "event_filter"

    def __init__(
        self,
        fomc_buffer: int = 1,
        opex_skip: bool = True,
        earnings_buffer: int = 0,
    ):
        """
        Args:
            fomc_buffer: Days before/after FOMC to skip
            opex_skip: Skip monthly options expiration (3rd Friday)
            earnings_buffer: Days before/after earnings to skip (requires context)
        """
        self.fomc_buffer = fomc_buffer
        self.opex_skip = opex_skip
        self.earnings_buffer = earnings_buffer

        # 2024-2025 FOMC meeting dates
        self.fomc_dates = {
            # 2024
            "2024-01-31",
            "2024-03-20",
            "2024-05-01",
            "2024-06-12",
            "2024-07-31",
            "2024-09-18",
            "2024-11-07",
            "2024-12-18",
            # 2025
            "2025-01-29",
            "2025-03-19",
            "2025-05-07",
            "2025-06-18",
            "2025-07-30",
            "2025-09-17",
            "2025-11-05",
            "2025-12-17",
        }

    def _is_near_fomc(self, date_str: str) -> Tuple[bool, str]:
        """Check if date is within FOMC buffer."""
        from datetime import datetime

        date = datetime.strptime(date_str, "%Y-%m-%d")

        for fomc_str in self.fomc_dates:
            fomc_date = datetime.strptime(fomc_str, "%Y-%m-%d")
            delta = abs((date - fomc_date).days)
            if delta <= self.fomc_buffer:
                return True, fomc_str

        return False, ""

    def _is_opex(self, date_str: str) -> bool:
        """Check if date is monthly options expiration (3rd Friday)."""
        from datetime import datetime

        date = datetime.strptime(date_str, "%Y-%m-%d")

        # Options expire on 3rd Friday of month
        if date.weekday() != 4:  # Not Friday
            return False

        # Check if it's the 3rd Friday (days 15-21)
        return 15 <= date.day <= 21

    def apply(
        self,
        symbol: str,
        date: str,
        data: pd.DataFrame,
        context: Optional[Dict] = None,
    ) -> FilterResult:
        # Check FOMC
        near_fomc, fomc_date = self._is_near_fomc(date)
        if near_fomc:
            return FilterResult(
                skip=True,
                reason=f"FOMC meeting on {fomc_date} (buffer: {self.fomc_buffer} days)",
                filter_name=self.name,
                data={"event": "fomc", "event_date": fomc_date},
            )

        # Check OpEx
        if self.opex_skip and self._is_opex(date):
            return FilterResult(
                skip=True,
                reason="Monthly options expiration (3rd Friday)",
                filter_name=self.name,
                data={"event": "opex"},
            )

        # Check earnings (requires context)
        if self.earnings_buffer and context and "earnings_dates" in context:
            earnings = context["earnings_dates"].get(symbol, [])
            from datetime import datetime

            date_dt = datetime.strptime(date, "%Y-%m-%d")
            for earn_date_str in earnings:
                earn_date = datetime.strptime(earn_date_str, "%Y-%m-%d")
                delta = abs((date_dt - earn_date).days)
                if delta <= self.earnings_buffer:
                    return FilterResult(
                        skip=True,
                        reason=f"Near earnings ({earn_date_str})",
                        filter_name=self.name,
                        data={"event": "earnings", "event_date": earn_date_str},
                    )

        return FilterResult()


class SpreadFilter(TradingFilter):
    """
    Avoid trading when bid-ask spreads are too wide.

    Wide spreads indicate:
    - Low liquidity
    - Market stress
    - Poor execution quality

    Note: Requires context with spread data (not always available in OHLCV)
    """

    name = "spread_filter"

    def __init__(self, max_spread_pct: float = 0.005):
        """
        Args:
            max_spread_pct: Maximum spread as percentage of price (0.005 = 0.5%)
        """
        self.max_spread_pct = max_spread_pct

    def apply(
        self,
        symbol: str,
        date: str,
        data: pd.DataFrame,
        context: Optional[Dict] = None,
    ) -> FilterResult:
        if not context or "spread" not in context:
            return FilterResult()  # No spread data, allow trading

        spread_pct = context["spread"]
        if spread_pct > self.max_spread_pct:
            return FilterResult(
                skip=True,
                reason=f"Spread {spread_pct:.2%} exceeds {self.max_spread_pct:.2%}",
                filter_name=self.name,
                data={"spread_pct": spread_pct},
            )

        return FilterResult()


class FilterManager:
    """
    Coordinates multiple trading filters.

    Usage:
        manager = FilterManager()
        manager.add_filter(VolumeFilter(threshold=0.5))
        manager.add_filter(VIXFilter(threshold=30))

        result = manager.apply_all(symbol, date, data, context)
        if result.skip:
            print(f"Skipping: {result.reason}")
    """

    def __init__(self):
        self.filters: List[TradingFilter] = []
        self.filter_stats: Dict[str, Dict] = {}

    def add_filter(self, filter_: TradingFilter):
        """Add a filter to the manager."""
        self.filters.append(filter_)
        self.filter_stats[filter_.name] = {"triggers": 0, "skip_count": 0}

    def remove_filter(self, filter_name: str):
        """Remove a filter by name."""
        self.filters = [f for f in self.filters if f.name != filter_name]

    def apply_all(
        self,
        symbol: str,
        date: str,
        data: pd.DataFrame,
        context: Optional[Dict] = None,
    ) -> FilterResult:
        """
        Apply all filters and return combined result.

        If any filter says skip, we skip.
        Size multipliers are combined multiplicatively.
        """
        combined = FilterResult()
        combined_multiplier = 1.0
        reasons = []

        for filter_ in self.filters:
            result = filter_.apply(symbol, date, data, context)

            if result.skip or result.size_multiplier < 1.0:
                self.filter_stats[filter_.name]["triggers"] += 1

            if result.skip:
                self.filter_stats[filter_.name]["skip_count"] += 1
                return FilterResult(
                    skip=True,
                    size_multiplier=0.0,
                    reason=result.reason,
                    filter_name=result.filter_name,
                    data=result.data,
                )

            if result.size_multiplier < 1.0:
                combined_multiplier *= result.size_multiplier
                reasons.append(result.reason)

        if combined_multiplier < 1.0:
            combined.size_multiplier = combined_multiplier
            combined.reason = "; ".join(reasons)

        return combined

    def get_stats(self) -> Dict[str, Dict]:
        """Get filter trigger statistics."""
        return self.filter_stats

    def reset_stats(self):
        """Reset filter statistics."""
        for name in self.filter_stats:
            self.filter_stats[name] = {"triggers": 0, "skip_count": 0}


# Convenience function for creating standard filter set
def create_standard_filters(
    volume_threshold: float = 0.5,
    gap_threshold: float = 0.02,
    vix_threshold: float = 30,
    skip_fomc: bool = True,
    skip_opex: bool = True,
) -> FilterManager:
    """
    Create a FilterManager with standard practical filters.

    Args:
        volume_threshold: Skip if volume < this % of average
        gap_threshold: Skip if gap > this %
        vix_threshold: Reduce sizing when VIX > this
        skip_fomc: Skip trading around FOMC meetings
        skip_opex: Skip monthly options expiration

    Returns:
        Configured FilterManager
    """
    manager = FilterManager()

    manager.add_filter(VolumeFilter(threshold=volume_threshold))
    manager.add_filter(GapFilter(threshold=gap_threshold))
    manager.add_filter(VIXFilter(threshold=vix_threshold))

    if skip_fomc or skip_opex:
        manager.add_filter(
            EventFilter(
                fomc_buffer=1 if skip_fomc else 0,
                opex_skip=skip_opex,
            )
        )

    return manager
