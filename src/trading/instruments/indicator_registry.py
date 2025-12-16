"""
Indicator Registry - Pluggable Technical Indicator System

Provides a registry pattern for technical indicators, enabling:
- Dynamic indicator loading and configuration
- Ranked voting with configurable active voters
- Easy addition of new indicators without code changes

Issue #364: Ranked Voter System for Technical Indicators
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

import pandas as pd

from .indicators import calculate_macd, calculate_rsi

logger = logging.getLogger(__name__)


@dataclass
class IndicatorResult:
    """Standardized result from any indicator calculation."""

    name: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 - 1.0
    strength: float  # Raw signal strength (indicator-specific scale)
    value: float  # Primary indicator value (e.g., RSI value, MACD histogram)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "action": self.action,
            "confidence": self.confidence,
            "strength": self.strength,
            "value": self.value,
            "metadata": self.metadata,
        }


class BaseIndicator(ABC):
    """
    Abstract base class for all technical indicators.

    All indicators must implement:
    - calculate(): Run indicator calculation on price data
    - get_signal(): Return standardized trading signal

    This enables pluggable indicators that can be ranked and voted.
    """

    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        """
        Initialize indicator with name and parameters.

        Args:
            name: Unique identifier for this indicator instance
            params: Configuration parameters (indicator-specific)
        """
        self.name = name
        self.params = params or {}
        self._last_calculation: Optional[Dict[str, pd.Series]] = None

    @property
    @abstractmethod
    def required_periods(self) -> int:
        """Minimum data points needed for reliable calculation."""
        pass

    @property
    @abstractmethod
    def default_params(self) -> Dict[str, Any]:
        """Default parameters for this indicator type."""
        pass

    @abstractmethod
    def calculate(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """
        Calculate indicator values from price series.

        Args:
            prices: Close price series

        Returns:
            Dictionary of calculated series (indicator-specific keys)
        """
        pass

    @abstractmethod
    def get_signal(self, prices: pd.Series) -> IndicatorResult:
        """
        Get trading signal from most recent data.

        Args:
            prices: Close price series

        Returns:
            IndicatorResult with action, confidence, and strength
        """
        pass

    def get_params(self) -> Dict[str, Any]:
        """Get current parameters (defaults merged with overrides)."""
        merged = self.default_params.copy()
        merged.update(self.params)
        return merged


class MACDIndicator(BaseIndicator):
    """
    MACD Indicator - Moving Average Convergence Divergence

    Validated parameters: 13/34/8 (Fibonacci optimized)
    Achieved 0.856 Sharpe ratio in backtesting.
    """

    def __init__(self, name: str = "MACD", params: Optional[Dict[str, Any]] = None):
        super().__init__(name, params)

    @property
    def required_periods(self) -> int:
        """Need slow period + signal period for reliable calculation."""
        p = self.get_params()
        return p["slow"] + p["signal"]

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "fast": 13,
            "slow": 34,
            "signal": 8,
            "threshold": 0.1,  # Histogram threshold for signal
        }

    def calculate(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """Calculate MACD using validated function."""
        p = self.get_params()
        result = calculate_macd(prices, fast=p["fast"], slow=p["slow"], signal=p["signal"])
        self._last_calculation = result
        return result

    def get_signal(self, prices: pd.Series) -> IndicatorResult:
        """Get MACD trading signal."""
        if len(prices) < self.required_periods:
            return IndicatorResult(
                name=self.name,
                action="HOLD",
                confidence=0.0,
                strength=0.0,
                value=0.0,
                metadata={"error": "Insufficient data"},
            )

        data = self.calculate(prices)
        histogram = data["histogram"].iloc[-1]
        threshold = self.get_params()["threshold"]

        if histogram > threshold:
            action = "BUY"
            confidence = 0.6
            strength = min(50.0, abs(histogram) * 10)
        elif histogram < -threshold:
            action = "SELL"
            confidence = 0.6
            strength = -min(50.0, abs(histogram) * 10)
        else:
            action = "HOLD"
            confidence = 0.3
            strength = 0.0

        return IndicatorResult(
            name=self.name,
            action=action,
            confidence=confidence,
            strength=strength,
            value=float(histogram),
            metadata={
                "macd_line": float(data["macd"].iloc[-1]),
                "signal_line": float(data["signal"].iloc[-1]),
                "histogram": float(histogram),
                "params": self.get_params(),
            },
        )


class RSIIndicator(BaseIndicator):
    """
    RSI Indicator - Relative Strength Index

    Validated parameters: 14-period, 30/70 thresholds
    Achieved 0.856 Sharpe ratio (combined with MACD) in backtesting.
    """

    def __init__(self, name: str = "RSI", params: Optional[Dict[str, Any]] = None):
        super().__init__(name, params)

    @property
    def required_periods(self) -> int:
        """Need period + buffer for reliable calculation."""
        return self.get_params()["period"] + 10

    @property
    def default_params(self) -> Dict[str, Any]:
        return {
            "period": 14,
            "oversold": 30,
            "overbought": 70,
        }

    def calculate(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """Calculate RSI using validated function."""
        p = self.get_params()
        result = calculate_rsi(
            prices,
            period=p["period"],
            oversold=p["oversold"],
            overbought=p["overbought"],
        )
        self._last_calculation = result
        return result

    def get_signal(self, prices: pd.Series) -> IndicatorResult:
        """Get RSI trading signal."""
        if len(prices) < self.required_periods:
            return IndicatorResult(
                name=self.name,
                action="HOLD",
                confidence=0.0,
                strength=0.0,
                value=50.0,
                metadata={"error": "Insufficient data"},
            )

        data = self.calculate(prices)
        p = self.get_params()
        rsi_value = data["rsi"].iloc[-1]

        if rsi_value < p["oversold"]:
            action = "BUY"
            confidence = 0.6
            strength = (p["oversold"] - rsi_value) * 3.33  # Scale to ~100
        elif rsi_value > p["overbought"]:
            action = "SELL"
            confidence = 0.6
            strength = -(rsi_value - p["overbought"]) * 3.33
        else:
            action = "HOLD"
            confidence = 0.3
            strength = 0.0

        return IndicatorResult(
            name=self.name,
            action=action,
            confidence=confidence,
            strength=strength,
            value=float(rsi_value),
            metadata={
                "rsi": float(rsi_value),
                "oversold": p["oversold"],
                "overbought": p["overbought"],
                "params": self.get_params(),
            },
        )


# Registry of available indicator classes
_INDICATOR_CLASSES: Dict[str, Type[BaseIndicator]] = {
    "MACD": MACDIndicator,
    "RSI": RSIIndicator,
}


class IndicatorRegistry:
    """
    Registry for managing technical indicators.

    Supports:
    - Registering new indicator types
    - Creating indicator instances with custom params
    - Tracking registered indicators for voting
    """

    def __init__(self):
        self._indicators: Dict[str, BaseIndicator] = {}
        self._indicator_classes: Dict[str, Type[BaseIndicator]] = _INDICATOR_CLASSES.copy()

    def register_class(self, name: str, indicator_class: Type[BaseIndicator]) -> None:
        """
        Register a new indicator class type.

        Args:
            name: Identifier for this indicator type
            indicator_class: Class that extends BaseIndicator
        """
        if not issubclass(indicator_class, BaseIndicator):
            raise TypeError(f"{indicator_class} must extend BaseIndicator")
        self._indicator_classes[name] = indicator_class
        logger.info(f"Registered indicator class: {name}")

    def create_indicator(
        self,
        indicator_type: str,
        name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> BaseIndicator:
        """
        Create an indicator instance.

        Args:
            indicator_type: Type of indicator (MACD, RSI, etc.)
            name: Instance name (defaults to type name)
            params: Override parameters

        Returns:
            Configured indicator instance
        """
        if indicator_type not in self._indicator_classes:
            raise ValueError(
                f"Unknown indicator type: {indicator_type}. "
                f"Available: {list(self._indicator_classes.keys())}"
            )

        indicator_class = self._indicator_classes[indicator_type]
        instance_name = name or indicator_type
        indicator = indicator_class(name=instance_name, params=params)

        self._indicators[instance_name] = indicator
        logger.debug(f"Created indicator: {instance_name} ({indicator_type})")
        return indicator

    def get_indicator(self, name: str) -> Optional[BaseIndicator]:
        """Get a registered indicator by name."""
        return self._indicators.get(name)

    def list_indicators(self) -> List[str]:
        """List all registered indicator instance names."""
        return list(self._indicators.keys())

    def list_available_types(self) -> List[str]:
        """List all available indicator types."""
        return list(self._indicator_classes.keys())

    def remove_indicator(self, name: str) -> bool:
        """Remove an indicator from the registry."""
        if name in self._indicators:
            del self._indicators[name]
            logger.debug(f"Removed indicator: {name}")
            return True
        return False

    def clear(self) -> None:
        """Clear all registered indicator instances."""
        self._indicators.clear()

    def get_all_signals(self, prices: pd.Series) -> Dict[str, IndicatorResult]:
        """
        Get signals from all registered indicators.

        Args:
            prices: Close price series

        Returns:
            Dictionary mapping indicator name to its signal result
        """
        results = {}
        for name, indicator in self._indicators.items():
            try:
                results[name] = indicator.get_signal(prices)
            except Exception as e:
                logger.error(f"Error getting signal from {name}: {e}")
                results[name] = IndicatorResult(
                    name=name,
                    action="HOLD",
                    confidence=0.0,
                    strength=0.0,
                    value=0.0,
                    metadata={"error": str(e)},
                )
        return results


# Global registry instance
_global_registry: Optional[IndicatorRegistry] = None


def get_indicator_registry() -> IndicatorRegistry:
    """Get the global indicator registry (singleton)."""
    global _global_registry
    if _global_registry is None:
        _global_registry = IndicatorRegistry()
    return _global_registry


def register_indicator_class(name: str, indicator_class: Type[BaseIndicator]) -> None:
    """Register an indicator class in the global registry."""
    get_indicator_registry().register_class(name, indicator_class)


def create_indicator(
    indicator_type: str,
    name: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> BaseIndicator:
    """Create an indicator in the global registry."""
    return get_indicator_registry().create_indicator(indicator_type, name, params)
