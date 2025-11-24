"""
Base Indicator Class for Technical Analysis

Provides common interface for all technical indicators in the ensemble voting system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict

import pandas as pd


@dataclass
class IndicatorSignal:
    """Standardized signal from a technical indicator"""

    indicator_name: str
    signal_strength: float  # -100 to +100
    confidence: float  # 0 to 1
    action: str  # "BUY", "SELL", "HOLD"
    reasoning: str
    metadata: Dict  # Additional indicator-specific data


class BaseIndicator(ABC):
    """
    Abstract base class for all technical indicators.

    Each indicator must:
    1. Calculate its technical values
    2. Generate trading signals (-100 to +100)
    3. Provide confidence scores (0-1)
    4. Integrate with cache system for performance
    """

    def __init__(self, name: str):
        """
        Initialize base indicator.

        Args:
            name: Indicator name for identification
        """
        self.name = name
        self._cache = None  # Will be set by VotingCoordinator

    def set_cache(self, cache_manager):
        """Set cache manager for performance optimization"""
        self._cache = cache_manager

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicator values from price data.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with indicator values added
        """
        pass

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> IndicatorSignal:
        """
        Generate trading signal from indicator values.

        Args:
            data: DataFrame with price and indicator data

        Returns:
            IndicatorSignal with strength, confidence, and action
        """
        pass

    def get_signal_strength(self, value: float, thresholds: Dict) -> float:
        """
        Convert indicator value to normalized signal strength.

        Args:
            value: Raw indicator value
            thresholds: Dict with buy/sell thresholds

        Returns:
            Signal strength from -100 to +100
        """
        # Common normalization logic
        if value <= thresholds.get("strong_buy", float("-inf")):
            return 100.0
        elif value <= thresholds.get("buy", float("-inf")):
            return 50.0
        elif value >= thresholds.get("strong_sell", float("inf")):
            return -100.0
        elif value >= thresholds.get("sell", float("inf")):
            return -50.0
        else:
            return 0.0  # Neutral

    def calculate_confidence(self, data: pd.DataFrame) -> float:
        """
        Calculate confidence score for the signal.

        Override in subclasses for indicator-specific logic.

        Args:
            data: DataFrame with indicator values

        Returns:
            Confidence score from 0 to 1
        """
        return 0.5  # Default moderate confidence
