"""
Technical Indicators - Pure Functions

Clean implementations of MACD and RSI using validated parameters.
All functions are pure (no side effects) for easy testing.
"""

from typing import Dict

import numpy as np
import pandas as pd


def calculate_macd(
    prices: pd.Series, fast: int = 13, slow: int = 34, signal: int = 8, timeframe: str = "1d"
) -> Dict[str, pd.Series]:
    """
    Calculate MACD with validated parameters (13/34/8).

    Args:
        prices: Price series (Close prices) - should be aggregated to the desired timeframe
        fast: Fast EMA period (default 13 - Fibonacci optimized)
        slow: Slow EMA period (default 34 - Fibonacci optimized)
        signal: Signal line EMA period (default 8 - Fibonacci optimized)
        timeframe: Analysis timeframe (Issue #365). This is informational for logging/debugging
                   Actual timeframe aggregation should be done before calling this function.
                   Supported values: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M
                   Default "1d" is validated and has 0.856 Sharpe ratio.

    Returns:
        Dictionary containing:
        - 'macd': MACD line (fast EMA - slow EMA)
        - 'signal': Signal line (EMA of MACD)
        - 'histogram': MACD histogram (MACD - Signal)
        - 'bullish': Boolean series indicating bullish signals (histogram > 0)
    """
    # Calculate EMAs
    fast_ema = prices.ewm(span=fast, adjust=False).mean()
    slow_ema = prices.ewm(span=slow, adjust=False).mean()

    # Calculate MACD line
    macd_line = fast_ema - slow_ema

    # Calculate signal line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    # Calculate histogram
    histogram = macd_line - signal_line

    # Bullish signal (validated: histogram > 0)
    bullish = histogram > 0

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram, "bullish": bullish}


def calculate_rsi(
    prices: pd.Series,
    period: int = 14,
    oversold: int = 30,
    overbought: int = 70,
    timeframe: str = "1d",
) -> Dict[str, pd.Series]:
    """
    Calculate RSI with validated parameters (14/30/70).

    Args:
        prices: Price series (Close prices) - should be aggregated to the desired timeframe
        period: RSI calculation period (default 14)
        oversold: Oversold threshold (default 30)
        overbought: Overbought threshold (default 70)
        timeframe: Analysis timeframe (Issue #365). This is informational for logging/debugging
                   Actual timeframe aggregation should be done before calling this function.
                   Supported values: 1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d, 1w, 1M
                   Default "1d" is validated and has 0.856 Sharpe ratio.

    Returns:
        Dictionary containing:
        - 'rsi': RSI values (0-100)
        - 'bullish': Boolean series indicating bullish signals (30 < RSI < 70)
        - 'oversold': Boolean series indicating oversold (RSI <= 30)
        - 'overbought': Boolean series indicating overbought (RSI >= 70)
    """
    # Calculate price changes
    delta = prices.diff()

    # Separate gains and losses
    gains = delta.where(delta > 0, 0)
    losses = -delta.where(delta < 0, 0)

    # Calculate average gains and losses
    avg_gains = gains.rolling(window=period).mean()
    avg_losses = losses.rolling(window=period).mean()

    # Calculate RS and RSI
    rs = avg_gains / avg_losses
    rsi = 100 - (100 / (1 + rs))

    # Signal logic (validated: not oversold/overbought)
    bullish = (rsi > oversold) & (rsi < overbought)
    oversold_signal = rsi <= oversold
    overbought_signal = rsi >= overbought

    return {
        "rsi": rsi,
        "bullish": bullish,
        "oversold": oversold_signal,
        "overbought": overbought_signal,
    }


def calculate_voting_consensus(macd_data: Dict, rsi_data: Dict) -> Dict[str, pd.Series]:
    """
    Calculate MACD+RSI voting consensus (validated system).

    Args:
        macd_data: MACD calculation results
        rsi_data: RSI calculation results

    Returns:
        Dictionary containing:
        - 'consensus': Boolean series where both indicators agree (bullish)
        - 'macd_votes': MACD bullish signals
        - 'rsi_votes': RSI bullish signals
        - 'confidence': Confidence score (0.0-1.0) based on indicator strength
    """
    macd_bullish = macd_data["bullish"]
    rsi_bullish = rsi_data["bullish"]

    # Voting consensus: both indicators must agree
    consensus = macd_bullish & rsi_bullish

    # Calculate confidence based on indicator strength
    # Higher MACD histogram = stronger signal
    # RSI closer to 50 = more neutral/stable
    macd_strength = np.abs(macd_data["histogram"]) / macd_data["histogram"].rolling(20).std()
    rsi_neutrality = 1 - np.abs(rsi_data["rsi"] - 50) / 50  # Closer to 50 = better

    confidence = ((macd_strength + rsi_neutrality) / 2).clip(0, 1)

    return {
        "consensus": consensus,
        "macd_votes": macd_bullish,
        "rsi_votes": rsi_bullish,
        "confidence": confidence,
    }


def calculate_kama(
    prices: pd.Series,
    lookback: int = 10,
    fast_period: int = 2,
    slow_period: int = 30,
    timeframe: str = "1w",
) -> Dict[str, pd.Series]:
    """
    Calculate Kaufman Adaptive Moving Average (KAMA).

    KAMA adapts its smoothing based on market efficiency - trending markets
    get a fast MA, choppy markets get a slow MA. This makes it ideal for
    weekly timeframes where noise filtering is critical.

    Args:
        prices: Price series (Close prices)
        lookback: Efficiency ratio calculation period (default 10)
        fast_period: Fast smoothing constant (default 2)
        slow_period: Slow smoothing constant (default 30)
        timeframe: Analysis timeframe (default "1w" for weekly)

    Returns:
        Dictionary containing:
        - 'kama': KAMA values
        - 'efficiency_ratio': Market efficiency (0-1, higher = trending)
        - 'smoothing': Current smoothing constant being applied
        - 'slope': KAMA slope (positive = bullish)
    """
    # Calculate efficiency ratio: direction / volatility
    direction = (prices - prices.shift(lookback)).abs()
    volatility = prices.diff().abs().rolling(window=lookback).sum()

    # Avoid division by zero
    efficiency_ratio = direction / volatility.replace(0, np.nan)
    efficiency_ratio = efficiency_ratio.fillna(0)

    # Calculate smoothing constants
    fast_sc = 2 / (fast_period + 1)
    slow_sc = 2 / (slow_period + 1)

    # Scaled smoothing constant: adapts based on efficiency
    scaled_sc = efficiency_ratio * (fast_sc - slow_sc) + slow_sc
    smoothing = scaled_sc**2  # Squared for additional smoothing

    # Calculate KAMA iteratively
    kama = pd.Series(index=prices.index, dtype=float)
    kama.iloc[lookback - 1] = prices.iloc[lookback - 1]  # Initialize

    for i in range(lookback, len(prices)):
        kama.iloc[i] = kama.iloc[i - 1] + smoothing.iloc[i] * (prices.iloc[i] - kama.iloc[i - 1])

    # Calculate slope (change over 6 periods for weekly)
    slope_period = 6 if timeframe == "1w" else 3
    slope = kama.diff(slope_period)

    return {
        "kama": kama,
        "efficiency_ratio": efficiency_ratio,
        "smoothing": smoothing,
        "slope": slope,
    }


def calculate_fold_ma(prices: pd.Series, periods: int = 5, fold_index: int = 2) -> pd.Series:
    """
    Calculate fold-based moving average (nth value from sorted window).

    This is a robust MA that uses the median-like approach: sort the window
    and pick the nth value. Less sensitive to outliers than SMA.

    Args:
        prices: Price series
        periods: Window size (default 5)
        fold_index: Which sorted value to use, 0-indexed (default 2 = 3rd lowest)

    Returns:
        Fold MA series
    """

    def fold_func(window):
        sorted_vals = sorted(window)
        return sorted_vals[min(fold_index, len(sorted_vals) - 1)]

    return prices.rolling(window=periods).apply(fold_func, raw=True)


def get_current_signals(prices: pd.Series) -> Dict:
    """
    Get current trading signals for most recent data point.

    Args:
        prices: Price series

    Returns:
        Dictionary with current signal state
    """
    if len(prices) < 34:  # Need at least slow EMA period
        return {
            "signal_strength": "INSUFFICIENT_DATA",
            "macd_bullish": False,
            "rsi_bullish": False,
            "consensus": False,
            "confidence": 0.0,
        }

    # Calculate indicators
    macd_data = calculate_macd(prices)
    rsi_data = calculate_rsi(prices)
    voting_data = calculate_voting_consensus(macd_data, rsi_data)

    # Get most recent values
    latest_idx = prices.index[-1]

    return {
        "date": latest_idx,
        "price": prices.iloc[-1],
        "macd_histogram": macd_data["histogram"].iloc[-1],
        "rsi_value": rsi_data["rsi"].iloc[-1],
        "macd_bullish": macd_data["bullish"].iloc[-1],
        "rsi_bullish": rsi_data["bullish"].iloc[-1],
        "consensus": voting_data["consensus"].iloc[-1],
        "confidence": voting_data["confidence"].iloc[-1],
        "signal_strength": "BULLISH" if voting_data["consensus"].iloc[-1] else "NEUTRAL",
    }
