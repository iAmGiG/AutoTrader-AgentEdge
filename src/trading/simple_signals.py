#!/usr/bin/env python3
"""
Simple Signal Generation

Simplified threshold-based signals for production trading.
Focuses on proven MACD+RSI voting without complex agent architecture.
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd

from config_defaults.trading_config import TradingConfig

from src.trading_tools.indicators import calculate_macd, calculate_rsi

logger = logging.getLogger(__name__)


class SimpleSignalGenerator:
    """
    Simple signal generator using proven MACD+RSI thresholds.

    This is the simplified version recommended for production use.
    No complex agent architecture - just threshold-based decisions.
    """

    def __init__(
        self,
        config: Optional[TradingConfig] = None,
        macd_fast: Optional[int] = None,
        macd_slow: Optional[int] = None,
        macd_signal: Optional[int] = None,
        rsi_period: Optional[int] = None,
        rsi_oversold: Optional[float] = None,
        rsi_overbought: Optional[float] = None,
        macd_threshold: Optional[float] = None,
        consensus_boost: Optional[float] = None,
    ):
        """
        Initialize with validated parameters from config system.

        Args:
            config: TradingConfig instance (loads defaults if None)
            Individual parameters override config values if provided
        """
        # Load config defaults
        if config is None:
            config = TradingConfig()

        # Use config values or individual overrides
        macd_config = config.get_macd_config()
        rsi_config = config.get_rsi_config()

        self.macd_fast = macd_fast or macd_config.fast
        self.macd_slow = macd_slow or macd_config.slow
        self.macd_signal = macd_signal or macd_config.signal
        self.rsi_period = rsi_period or rsi_config.period
        self.rsi_oversold = rsi_oversold or rsi_config.oversold
        self.rsi_overbought = rsi_overbought or rsi_config.overbought
        self.macd_threshold = macd_threshold or 0.1  # Default threshold
        self.consensus_boost = consensus_boost or 0.15  # Default boost

        logger.info("SimpleSignalGenerator initialized:")
        logger.info(f"  MACD: {self.macd_fast}/{self.macd_slow}/{self.macd_signal}")
        logger.info(
            f"  RSI: {self.rsi_period} period, {self.rsi_oversold}/{self.rsi_overbought} levels"
        )
        logger.info(f"  Thresholds: MACD {self.macd_threshold}, consensus {self.consensus_boost}")

    def evaluate_signal(self, price_data: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict[str, Any]:
        """
        Generate trading signal using simple thresholds.

        Args:
            price_data: DataFrame with OHLCV data
            symbol: Symbol for logging

        Returns:
            Signal dict with action, confidence, and reasoning
        """
        try:
            if len(price_data) < max(self.macd_slow + self.macd_signal, self.rsi_period):
                return {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reason": "Insufficient data for indicators",
                    "raw_data": {},
                }

            # Calculate indicators (functions expect Series, return Dict)
            close_prices = (
                price_data["close"] if "close" in price_data.columns else price_data["Close"]
            )

            macd_data = calculate_macd(
                close_prices,
                fast=self.macd_fast,
                slow=self.macd_slow,
                signal=self.macd_signal,
            )

            rsi_data = calculate_rsi(close_prices, period=self.rsi_period)

            # Get latest values from dict returns
            latest_macd = macd_data["macd"].iloc[-1]
            latest_macd_signal = macd_data["signal"].iloc[-1]
            latest_rsi = rsi_data["rsi"].iloc[-1]
            macd_crossover = latest_macd - latest_macd_signal

            # Raw technical data
            raw_data = {
                "macd_line": latest_macd,
                "macd_signal": latest_macd_signal,
                "macd_crossover": macd_crossover,
                "rsi": latest_rsi,
                "price": close_prices.iloc[-1],
            }

            # Simple threshold decisions
            signals = []
            reasons = []

            # MACD Signal
            if macd_crossover > self.macd_threshold:
                signals.append("BUY")
                reasons.append(f"MACD crossover: {macd_crossover:.3f} > {self.macd_threshold}")
            elif macd_crossover < -self.macd_threshold:
                signals.append("SELL")
                reasons.append(f"MACD crossover: {macd_crossover:.3f} < -{self.macd_threshold}")
            else:
                signals.append("HOLD")
                reasons.append(f"MACD neutral: {macd_crossover:.3f}")

            # RSI Signal
            if latest_rsi < self.rsi_oversold:
                signals.append("BUY")
                reasons.append(f"RSI oversold: {latest_rsi:.1f} < {self.rsi_oversold}")
            elif latest_rsi > self.rsi_overbought:
                signals.append("SELL")
                reasons.append(f"RSI overbought: {latest_rsi:.1f} > {self.rsi_overbought}")
            else:
                signals.append("HOLD")
                reasons.append(f"RSI neutral: {latest_rsi:.1f}")

            # Voting logic
            buy_votes = signals.count("BUY")
            sell_votes = signals.count("SELL")

            if buy_votes > sell_votes:
                action = "BUY"
                base_confidence = 0.6 + (buy_votes - sell_votes) * 0.1
                # Consensus boost when both agree
                if buy_votes == 2:
                    base_confidence += self.consensus_boost
            elif sell_votes > buy_votes:
                action = "SELL"
                base_confidence = 0.6 + (sell_votes - buy_votes) * 0.1
                # Consensus boost when both agree
                if sell_votes == 2:
                    base_confidence += self.consensus_boost
            else:
                action = "HOLD"
                base_confidence = 0.3

            # Cap confidence at 1.0
            confidence = min(base_confidence, 1.0)

            reason = f"Voting: {buy_votes} BUY, {sell_votes} SELL. " + "; ".join(reasons)

            logger.debug(f"{symbol} signal: {action} ({confidence:.2f}) - {reason}")

            return {
                "action": action,
                "confidence": confidence,
                "reason": reason,
                "raw_data": raw_data,
                "votes": {"buy": buy_votes, "sell": sell_votes, "hold": signals.count("HOLD")},
            }

        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reason": f"Error: {str(e)}",
                "raw_data": {},
            }

    def get_signal_summary(self, signal: Dict[str, Any]) -> str:
        """
        Get human-readable signal summary.

        Args:
            signal: Signal dict from evaluate_signal()

        Returns:
            Formatted summary string
        """
        action = signal["action"]
        confidence = signal["confidence"]
        raw = signal.get("raw_data", {})

        summary = f"{action} ({confidence:.1%})"

        if raw:
            summary += f" | MACD: {raw.get('macd_crossover', 0):.3f}"
            summary += f" | RSI: {raw.get('rsi', 0):.1f}"

        return summary

    def is_actionable_signal(self, signal: Dict[str, Any], min_confidence: float = 0.6) -> bool:
        """
        Check if signal is strong enough to act on.

        Args:
            signal: Signal dict from evaluate_signal()
            min_confidence: Minimum confidence threshold

        Returns:
            True if signal should trigger trading action
        """
        return signal["action"] in ["BUY", "SELL"] and signal["confidence"] >= min_confidence


# Convenience function for simple usage


def get_simple_signal(price_data: pd.DataFrame, symbol: str = "UNKNOWN") -> Dict[str, Any]:
    """
    Get a simple trading signal using default validated parameters.

    Args:
        price_data: DataFrame with OHLCV data
        symbol: Symbol for logging

    Returns:
        Signal dict with action, confidence, and reasoning
    """
    generator = SimpleSignalGenerator()
    return generator.evaluate_signal(price_data, symbol)
