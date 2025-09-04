"""
Simple RSI Indicator for Voting Strategy

RSI signal generator using efficient indicator_library.rsi() calculation.
Provides IndicatorSignal interface with buy/sell/hold decisions and confidence scores.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from .base_indicator import BaseIndicator, IndicatorSignal
from .indicator_library import rsi


class SimpleRSI(BaseIndicator):
    """
    Simple RSI (Relative Strength Index) implementation.
    
    Standard 14-period RSI with basic buy/sell thresholds:
    - RSI < 30: Oversold (BUY signal)
    - RSI > 70: Overbought (SELL signal)
    - 30 <= RSI <= 70: Neutral (HOLD signal)
    """
    
    def __init__(self, period: int = 14, oversold: float = 30, overbought: float = 70):
        """
        Initialize RSI indicator.
        
        Args:
            period: RSI calculation period (default 14)
            oversold: Oversold threshold for buy signals (default 30)
            overbought: Overbought threshold for sell signals (default 70)
        """
        super().__init__("RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate RSI values from price data using efficient indicator library.
        
        Args:
            data: DataFrame with OHLCV data (needs 'close' column)
            
        Returns:
            DataFrame with RSI values added
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column for RSI calculation")
            
        # Use fast numpy-based RSI calculation from indicator library
        rsi_values = rsi(data['close'], period=self.period)
        
        # Add to dataframe
        result = data.copy()
        result['rsi'] = rsi_values
        result['rsi_signal'] = self._calculate_signal_strength(rsi_values)
        
        return result
        
    def generate_signal(self, data: pd.DataFrame) -> IndicatorSignal:
        """
        Generate trading signal from RSI values.
        
        Args:
            data: DataFrame with RSI values
            
        Returns:
            IndicatorSignal with action, strength, and confidence
        """
        if 'rsi' not in data.columns:
            data = self.calculate(data)
            
        # Get latest RSI value
        latest_rsi = data['rsi'].iloc[-1]
        
        # Handle NaN (not enough data)
        if pd.isna(latest_rsi):
            return IndicatorSignal(
                indicator_name=self.name,
                signal_strength=0.0,
                confidence=0.0,
                action="HOLD",
                reasoning="Insufficient data for RSI calculation",
                metadata={"rsi": None, "period": self.period}
            )
            
        # Generate signal based on thresholds
        if latest_rsi <= self.oversold:
            signal_strength = 50.0  # Moderate buy signal
            action = "BUY"
            reasoning = f"RSI oversold: {latest_rsi:.1f} <= {self.oversold}"
        elif latest_rsi >= self.overbought:
            signal_strength = -50.0  # Moderate sell signal  
            action = "SELL"
            reasoning = f"RSI overbought: {latest_rsi:.1f} >= {self.overbought}"
        else:
            signal_strength = 0.0
            action = "HOLD"
            reasoning = f"RSI neutral: {latest_rsi:.1f} (between {self.oversold}-{self.overbought})"
            
        # Calculate confidence based on how extreme the RSI is
        confidence = self._calculate_confidence_score(latest_rsi)
        
        return IndicatorSignal(
            indicator_name=self.name,
            signal_strength=signal_strength,
            confidence=confidence,
            action=action,
            reasoning=reasoning,
            metadata={
                "rsi": latest_rsi,
                "period": self.period,
                "oversold_threshold": self.oversold,
                "overbought_threshold": self.overbought
            }
        )
        
    def _calculate_signal_strength(self, rsi_series: pd.Series) -> pd.Series:
        """Calculate signal strength for entire series"""
        signals = pd.Series(index=rsi_series.index, dtype=float)
        
        # Oversold signals (positive)
        signals.loc[rsi_series <= self.oversold] = 50.0
        
        # Overbought signals (negative)  
        signals.loc[rsi_series >= self.overbought] = -50.0
        
        # Neutral signals
        mask = (rsi_series > self.oversold) & (rsi_series < self.overbought)
        signals.loc[mask] = 0.0
        
        return signals
        
    def _calculate_confidence_score(self, rsi_value: float) -> float:
        """
        Calculate confidence score based on RSI extremeness.
        
        Args:
            rsi_value: Current RSI value
            
        Returns:
            Confidence score from 0 to 1
        """
        if pd.isna(rsi_value):
            return 0.0
            
        # More extreme RSI = higher confidence
        if rsi_value <= self.oversold:
            # More oversold = higher confidence (max at RSI=0)
            confidence = min(1.0, (self.oversold - rsi_value) / self.oversold)
            return max(0.5, confidence)  # Minimum 50% confidence
            
        elif rsi_value >= self.overbought:
            # More overbought = higher confidence (max at RSI=100)
            confidence = min(1.0, (rsi_value - self.overbought) / (100 - self.overbought))
            return max(0.5, confidence)  # Minimum 50% confidence
            
        else:
            # Neutral zone = low confidence
            return 0.3
            
    def get_signal_summary(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Get summary of RSI signals over the data period.
        
        Args:
            data: DataFrame with price data
            
        Returns:
            Dictionary with RSI summary statistics
        """
        if 'rsi' not in data.columns:
            data = self.calculate(data)
            
        rsi_series = data['rsi'].dropna()
        
        if len(rsi_series) == 0:
            return {"error": "No RSI data available"}
            
        # Count signals
        oversold_count = (rsi_series <= self.oversold).sum()
        overbought_count = (rsi_series >= self.overbought).sum()
        neutral_count = len(rsi_series) - oversold_count - overbought_count
        
        return {
            "indicator": self.name,
            "period": self.period,
            "data_points": len(rsi_series),
            "avg_rsi": float(rsi_series.mean()),
            "min_rsi": float(rsi_series.min()),
            "max_rsi": float(rsi_series.max()),
            "oversold_signals": int(oversold_count),
            "overbought_signals": int(overbought_count),
            "neutral_signals": int(neutral_count),
            "signal_ratio": {
                "oversold_pct": float(oversold_count / len(rsi_series) * 100),
                "overbought_pct": float(overbought_count / len(rsi_series) * 100),
                "neutral_pct": float(neutral_count / len(rsi_series) * 100)
            }
        }