"""
Technical Indicators - Pure Functions

Clean implementations of MACD and RSI using validated parameters.
All functions are pure (no side effects) for easy testing.
"""

from typing import Dict

import numpy as np
import pandas as pd


def calculate_macd(
    prices: pd.Series, fast: int = 13, slow: int = 34, signal: int = 8
) -> Dict[str, pd.Series]:
    """
    Calculate MACD with validated parameters (13/34/8).

    Args:
        prices: Price series (Close prices)
        fast: Fast EMA period (default 13 - Fibonacci optimized)
        slow: Slow EMA period (default 34 - Fibonacci optimized)
        signal: Signal line EMA period (default 8 - Fibonacci optimized)

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
    prices: pd.Series, period: int = 14, oversold: int = 30, overbought: int = 70
) -> Dict[str, pd.Series]:
    """
    Calculate RSI with validated parameters (14/30/70).

    Args:
        prices: Price series (Close prices)
        period: RSI calculation period (default 14)
        oversold: Oversold threshold (default 30)
        overbought: Overbought threshold (default 70)

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
