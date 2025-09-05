"""
Fibonacci Regime Module - Phase 1 Implementation

Implements basic FibonacciRegimeModule with 34 EMA filtering
without disrupting the proven voting system.

Based on Carolyn Borden's Fibonacci Trading methodology and 
validated parameters from MACD optimization (13/34/8).
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class FibonacciRegimeModule:
    """
    Modular regime detection using Fibonacci timeframes.
    
    Phase 1: Implements 34 EMA filter to enhance existing voting signals.
    Future phases will add CCI filters and symmetry detection.
    """
    
    # Fibonacci sequence periods
    FIB_PERIODS = [8, 13, 21, 34, 55, 89, 144, 233]
    
    # Primary Fibonacci parameters (validated from MACD optimization)
    FAST_FIB = 13
    SLOW_FIB = 34
    SIGNAL_FIB = 8
    
    def __init__(self, primary_period: int = 34):
        """
        Initialize Fibonacci Regime Module.
        
        Args:
            primary_period: Primary EMA period for filtering (default: 34)
        """
        self.primary_period = primary_period
        self.regime_history = []
        
        logger.info(f"FibonacciRegimeModule initialized with {primary_period} EMA filter")
        
    def calculate_ema(self, data: pd.DataFrame, period: int) -> pd.Series:
        """
        Calculate Exponential Moving Average.
        
        Args:
            data: DataFrame with price data
            period: EMA period
            
        Returns:
            EMA series
        """
        if 'close' not in data.columns:
            raise ValueError("DataFrame must contain 'close' column")
            
        return data['close'].ewm(span=period, adjust=False).mean()
        
    def detect_regime(self, data: pd.DataFrame) -> str:
        """
        Detect market regime using multiple Fibonacci EMAs.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            Regime classification: STRONG_BULL, STRONG_BEAR, or TRANSITIONAL
        """
        if len(data) < 89:  # Need at least 89 periods for analysis
            return "UNKNOWN"
            
        try:
            # Calculate key Fibonacci EMAs
            ema_13 = self.calculate_ema(data, 13)
            ema_34 = self.calculate_ema(data, 34)
            ema_55 = self.calculate_ema(data, 55)
            ema_89 = self.calculate_ema(data, 89)
            
            # Get latest values
            current_price = data['close'].iloc[-1]
            ema_13_val = ema_13.iloc[-1]
            ema_34_val = ema_34.iloc[-1]
            ema_55_val = ema_55.iloc[-1]
            ema_89_val = ema_89.iloc[-1]
            
            # Regime detection based on EMA alignment
            if (current_price > ema_13_val > ema_34_val > ema_55_val > ema_89_val):
                regime = "STRONG_BULL"
            elif (current_price < ema_13_val < ema_34_val < ema_55_val < ema_89_val):
                regime = "STRONG_BEAR"
            elif current_price > ema_34_val and ema_13_val > ema_34_val:
                regime = "BULL"
            elif current_price < ema_34_val and ema_13_val < ema_34_val:
                regime = "BEAR"
            else:
                regime = "TRANSITIONAL"
                
            # Store regime history
            self.regime_history.append({
                "timestamp": datetime.now().isoformat(),
                "regime": regime,
                "price": current_price,
                "ema_34": ema_34_val
            })
            
            return regime
            
        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return "UNKNOWN"
            
    def apply_ema_filter(self, data: pd.DataFrame, signal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply 34 EMA filter to trading signal (Phase 1 core functionality).
        
        Rules:
        - BUY signals: Only valid if price > EMA34
        - SELL signals: Only valid if price < EMA34
        - HOLD: No change
        
        Args:
            data: DataFrame with OHLCV data
            signal: Original trading signal
            
        Returns:
            Filtered signal with regime information
        """
        if len(data) < self.primary_period:
            signal["fibonacci_filter"] = "INSUFFICIENT_DATA"
            return signal
            
        try:
            # Calculate primary EMA
            ema_34 = self.calculate_ema(data, self.primary_period)
            current_price = data['close'].iloc[-1]
            ema_34_val = ema_34.iloc[-1]
            
            # Apply filter based on signal action
            original_action = signal.get("action", "HOLD")
            filtered_action = original_action
            filter_status = "PASS"
            
            # Calculate distance from EMA34 as a percentage
            price_ema_ratio = current_price / ema_34_val
            distance_pct = abs(price_ema_ratio - 1.0) * 100
            
            if original_action == "BUY":
                if current_price <= ema_34_val:
                    # Price below EMA34 - reduce position size but don't completely block
                    if distance_pct > 5.0:  # More than 5% below EMA34
                        filtered_action = "HOLD"
                        filter_status = "BLOCKED"
                        signal["confidence"] *= 0.3
                    else:
                        # Close to EMA34, allow with reduced size
                        signal["position_size"] = signal.get("position_size", 1.0) * 0.5
                        signal["confidence"] *= 0.7
                        filter_status = "REDUCED"
                    signal["reasoning"] += f" | Fibonacci filter: Price ({current_price:.2f}) {distance_pct:.1f}% below EMA34 ({ema_34_val:.2f})"
                else:
                    signal["confidence"] = min(1.0, signal.get("confidence", 0.5) * 1.1)  # Boost confidence slightly
                    signal["reasoning"] += f" | Fibonacci filter: Price ({current_price:.2f}) above EMA34 ({ema_34_val:.2f}) ✓"
                    
            elif original_action == "SELL":
                if current_price >= ema_34_val:
                    # Price above EMA34 - reduce position size but don't completely block strong signals
                    if distance_pct > 5.0 and signal.get("confidence", 0.5) < 0.8:  # More than 5% above EMA34 AND weak signal
                        filtered_action = "HOLD"
                        filter_status = "BLOCKED"
                        signal["confidence"] *= 0.3
                    else:
                        # Close to EMA34 or strong signal, allow with reduced size
                        signal["position_size"] = signal.get("position_size", 1.0) * 0.5
                        signal["confidence"] *= 0.7
                        filter_status = "REDUCED"
                    signal["reasoning"] += f" | Fibonacci filter: Price ({current_price:.2f}) {distance_pct:.1f}% above EMA34 ({ema_34_val:.2f})"
                else:
                    signal["confidence"] = min(1.0, signal.get("confidence", 0.5) * 1.1)
                    signal["reasoning"] += f" | Fibonacci filter: Price ({current_price:.2f}) below EMA34 ({ema_34_val:.2f}) ✓"
                    
            # Update signal with filter information
            signal["action"] = filtered_action
            signal["fibonacci_filter"] = {
                "status": filter_status,
                "original_action": original_action,
                "filtered_action": filtered_action,
                "price": current_price,
                "ema_34": ema_34_val,
                "price_vs_ema": "ABOVE" if current_price > ema_34_val else "BELOW"
            }
            
            # Add regime information
            regime = self.detect_regime(data)
            signal["market_regime"] = regime
            
            return signal
            
        except Exception as e:
            logger.error(f"Error applying EMA filter: {e}")
            signal["fibonacci_filter"] = f"ERROR: {str(e)}"
            return signal
            
    def calculate_fibonacci_retracements(self, data: pd.DataFrame, lookback: int = 100) -> Dict[str, float]:
        """
        Calculate Fibonacci retracement levels from recent high/low.
        
        Args:
            data: DataFrame with OHLCV data
            lookback: Number of periods to look back for high/low
            
        Returns:
            Dictionary with Fibonacci levels
        """
        if len(data) < lookback:
            lookback = len(data)
            
        recent_data = data.tail(lookback)
        high = recent_data['high'].max()
        low = recent_data['low'].min()
        diff = high - low
        
        # Standard Fibonacci ratios
        levels = {
            "0.0%": high,
            "23.6%": high - (diff * 0.236),
            "38.2%": high - (diff * 0.382),
            "50.0%": high - (diff * 0.500),
            "61.8%": high - (diff * 0.618),
            "78.6%": high - (diff * 0.786),
            "100.0%": low
        }
        
        return levels
        
    def analyze_fibonacci_confluence(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze confluence of multiple Fibonacci indicators.
        
        Args:
            data: DataFrame with OHLCV data
            
        Returns:
            Confluence analysis results
        """
        results = {
            "regime": self.detect_regime(data),
            "retracements": {},
            "ema_positions": {},
            "confluence_score": 0.0
        }
        
        if len(data) < 89:
            results["status"] = "INSUFFICIENT_DATA"
            return results
            
        try:
            # Get current price
            current_price = data['close'].iloc[-1]
            
            # Calculate retracement levels
            retracements = self.calculate_fibonacci_retracements(data)
            results["retracements"] = retracements
            
            # Check price position relative to key Fibonacci EMAs
            for period in [13, 34, 55, 89]:
                if len(data) >= period:
                    ema_val = self.calculate_ema(data, period).iloc[-1]
                    results["ema_positions"][f"EMA{period}"] = {
                        "value": ema_val,
                        "price_position": "ABOVE" if current_price > ema_val else "BELOW"
                    }
                    
            # Calculate confluence score (simplified for Phase 1)
            bullish_count = sum(1 for pos in results["ema_positions"].values() 
                              if pos["price_position"] == "ABOVE")
            results["confluence_score"] = bullish_count / len(results["ema_positions"])
            
            # Add interpretation
            if results["confluence_score"] > 0.75:
                results["interpretation"] = "STRONG_BULLISH_CONFLUENCE"
            elif results["confluence_score"] > 0.5:
                results["interpretation"] = "BULLISH_CONFLUENCE"
            elif results["confluence_score"] > 0.25:
                results["interpretation"] = "NEUTRAL_CONFLUENCE"
            else:
                results["interpretation"] = "BEARISH_CONFLUENCE"
                
            results["status"] = "SUCCESS"
            
        except Exception as e:
            logger.error(f"Error analyzing Fibonacci confluence: {e}")
            results["status"] = f"ERROR: {str(e)}"
            
        return results
        
    def get_regime_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about regime detection history.
        
        Returns:
            Dictionary with regime statistics
        """
        if not self.regime_history:
            return {"message": "No regime history available"}
            
        regimes = [h["regime"] for h in self.regime_history]
        
        stats = {
            "total_observations": len(regimes),
            "regime_counts": {
                regime: regimes.count(regime) 
                for regime in set(regimes)
            },
            "current_regime": regimes[-1] if regimes else "UNKNOWN",
            "regime_percentages": {}
        }
        
        # Calculate percentages
        for regime, count in stats["regime_counts"].items():
            stats["regime_percentages"][regime] = (count / len(regimes)) * 100
            
        return stats