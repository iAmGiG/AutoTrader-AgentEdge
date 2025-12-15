"""
Entry Planning Indicators (Issue #366)

OHLCV-based functions for dynamic entry planning with ATR-based stops,
support/resistance detection, and volume confirmation.

All functions are pure (no side effects) for easy testing.
"""

from typing import Dict, Optional

import pandas as pd


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Calculate Average True Range (ATR) for volatility-based stops.

    ATR measures market volatility by decomposing the entire range of an asset
    price for that period. Used for dynamic stop-loss placement.

    Args:
        high: High prices series
        low: Low prices series
        close: Close prices series
        period: ATR calculation period (default 14)

    Returns:
        ATR values as pd.Series
    """
    prev_close = close.shift(1)

    # True Range is the greatest of:
    # 1. Current High - Current Low
    # 2. |Current High - Previous Close|
    # 3. |Current Low - Previous Close|
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()

    return atr


def find_support_resistance(
    high: pd.Series,
    low: pd.Series,
    lookback: int = 20,
) -> Dict[str, float]:
    """
    Find recent support and resistance levels from swing highs/lows.

    Simple approach using recent price extremes. For intraday entry planning,
    identifies key levels where price has historically reversed.

    Args:
        high: High prices series
        low: Low prices series
        lookback: Number of periods to look back (default 20)

    Returns:
        Dictionary containing:
        - 'support': Recent support level (lowest low)
        - 'resistance': Recent resistance level (highest high)
        - 'range': Price range between support and resistance
    """
    recent_high = high.tail(lookback)
    recent_low = low.tail(lookback)

    support = recent_low.min()
    resistance = recent_high.max()

    return {
        "support": support,
        "resistance": resistance,
        "range": resistance - support,
    }


def calculate_volume_confirmation(
    volume: pd.Series,
    lookback: int = 20,
) -> Dict[str, float]:
    """
    Calculate volume metrics for entry confirmation.

    Volume confirmation helps validate breakouts and signal strength.
    Higher volume during moves indicates stronger conviction.

    Args:
        volume: Volume series
        lookback: Periods for average volume calculation (default 20)

    Returns:
        Dictionary containing:
        - 'current_volume': Most recent volume
        - 'avg_volume': Average volume over lookback period
        - 'volume_ratio': Current vs average (>1 = above average)
        - 'above_average': Boolean, True if current > average
        - 'high_volume': Boolean, True if ratio > 1.5
    """
    avg_volume = volume.rolling(window=lookback).mean()
    current_volume = volume.iloc[-1]
    avg_vol_value = avg_volume.iloc[-1]

    volume_ratio = current_volume / avg_vol_value if avg_vol_value > 0 else 1.0

    return {
        "current_volume": current_volume,
        "avg_volume": avg_vol_value,
        "volume_ratio": volume_ratio,
        "above_average": volume_ratio > 1.0,
        "high_volume": volume_ratio > 1.5,
    }


def _calculate_quality_score(
    vol_data: Dict, sr_levels: Dict, current_price: float, signal_direction: str
) -> str:
    """Calculate plan quality based on volume and price position."""
    quality_score = 0

    # Volume confirmation adds to quality
    if vol_data["above_average"]:
        quality_score += 1
    if vol_data["high_volume"]:
        quality_score += 1

    # Price position relative to support/resistance
    price_range = sr_levels["range"]
    if price_range > 0:
        quality_score += _score_price_position(
            current_price, sr_levels, price_range, signal_direction
        )

    # Map score to quality label
    if quality_score >= 3:
        return "STRONG"
    elif quality_score >= 1:
        return "MODERATE"
    return "WEAK"


def _score_price_position(
    current_price: float, sr_levels: Dict, price_range: float, signal_direction: str
) -> int:
    """Score price position relative to support/resistance."""
    if signal_direction == "BUY":
        dist_to_support = (current_price - sr_levels["support"]) / price_range
        if dist_to_support < 0.3:
            return 2
        elif dist_to_support < 0.5:
            return 1
    else:
        dist_to_resistance = (sr_levels["resistance"] - current_price) / price_range
        if dist_to_resistance < 0.3:
            return 2
        elif dist_to_resistance < 0.5:
            return 1
    return 0


def _calculate_stop_target(
    current_price: float,
    stop_distance: float,
    risk_reward_ratio: float,
    sr_levels: Dict,
    signal_direction: str,
) -> tuple[float, float]:
    """Calculate stop loss and take profit levels."""
    if signal_direction == "BUY":
        stop_loss = round(current_price - stop_distance, 2)
        take_profit = round(current_price + (stop_distance * risk_reward_ratio), 2)
        # Adjust stop if support is closer
        if sr_levels["support"] > stop_loss:
            stop_loss = round(sr_levels["support"] * 0.995, 2)
    else:
        stop_loss = round(current_price + stop_distance, 2)
        take_profit = round(current_price - (stop_distance * risk_reward_ratio), 2)
        # Adjust stop if resistance is closer
        if sr_levels["resistance"] < stop_loss:
            stop_loss = round(sr_levels["resistance"] * 1.005, 2)

    return stop_loss, take_profit


def calculate_entry_plan(
    ohlcv: pd.DataFrame,
    current_price: float,
    signal_direction: str,
    atr_multiplier: float = 2.0,
    risk_reward_ratio: float = 2.0,
) -> Dict[str, Optional[float]]:
    """
    Generate a complete entry plan using OHLCV data.

    Combines ATR-based stops, support/resistance awareness, and volume
    confirmation to produce dynamic entry/exit levels.

    Args:
        ohlcv: DataFrame with Open, High, Low, Close, Volume columns
        current_price: Current market price for the entry
        signal_direction: 'BUY' or 'SELL'
        atr_multiplier: ATR multiplier for stop distance (default 2.0)
        risk_reward_ratio: Target profit / risk ratio (default 2.0)

    Returns:
        Dictionary containing entry_price, stop_loss, take_profit, atr_value,
        support, resistance, volume_confirmation, and plan_quality.
    """
    if len(ohlcv) < 20:
        return _insufficient_data_result()

    # Calculate indicators
    atr = calculate_atr(ohlcv["High"], ohlcv["Low"], ohlcv["Close"])
    current_atr = atr.iloc[-1]
    sr_levels = find_support_resistance(ohlcv["High"], ohlcv["Low"])
    vol_data = calculate_volume_confirmation(ohlcv["Volume"])

    # Validate signal direction
    if signal_direction not in ("BUY", "SELL"):
        return _no_signal_result(current_atr, sr_levels)

    # Calculate stop and target
    stop_distance = current_atr * atr_multiplier
    stop_loss, take_profit = _calculate_stop_target(
        current_price, stop_distance, risk_reward_ratio, sr_levels, signal_direction
    )

    # Determine plan quality
    plan_quality = _calculate_quality_score(vol_data, sr_levels, current_price, signal_direction)

    return {
        "entry_price": round(current_price, 2),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "atr_value": round(current_atr, 4),
        "support": round(sr_levels["support"], 2),
        "resistance": round(sr_levels["resistance"], 2),
        "volume_confirmation": vol_data["above_average"],
        "plan_quality": plan_quality,
    }


def _insufficient_data_result() -> Dict[str, Optional[float]]:
    """Return result for insufficient data case."""
    return {
        "entry_price": None,
        "stop_loss": None,
        "take_profit": None,
        "atr_value": None,
        "support": None,
        "resistance": None,
        "volume_confirmation": False,
        "plan_quality": "INSUFFICIENT_DATA",
    }


def _no_signal_result(current_atr: float, sr_levels: Dict) -> Dict[str, Optional[float]]:
    """Return result for invalid signal direction."""
    return {
        "entry_price": None,
        "stop_loss": None,
        "take_profit": None,
        "atr_value": current_atr,
        "support": sr_levels["support"],
        "resistance": sr_levels["resistance"],
        "volume_confirmation": False,
        "plan_quality": "NO_SIGNAL",
    }
