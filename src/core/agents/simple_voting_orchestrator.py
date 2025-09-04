"""
Simple Voting Orchestrator - No AutoGen Dependencies

Simplified version for testing that doesn't inherit from BaseAgent.
Focuses on getting ONE working voting strategy with real 2024 data.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime

# Direct imports without AutoGen dependencies
from ..indicators.simple_rsi import SimpleRSI
from ...data.cache.unified_cache import UnifiedCacheManager

logger = logging.getLogger(__name__)


class SimpleVotingOrchestrator:
    """
    Simplified voting orchestrator for MACD + RSI without AutoGen dependencies.
    
    This is a streamlined version focused on getting one working strategy.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize the simple voting orchestrator."""
        self.config = config or {}
        
        # Initialize cache
        self.cache = UnifiedCacheManager()
        
        # Initialize RSI indicator
        self.rsi_indicator = SimpleRSI(period=14, oversold=30, overbought=70)
        
        # Track decisions
        self.decision_history = []
        
        logger.info("SimpleVotingOrchestrator initialized")
        
    def get_market_data(self, symbol: str, date: str) -> Optional[pd.DataFrame]:
        """
        Get market data using the cache system.
        
        Args:
            symbol: Stock symbol
            date: Date string (YYYY-MM-DD)
            
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Calculate date range (need broader range for indicators)
            from datetime import datetime, timedelta
            target_date = datetime.strptime(date, '%Y-%m-%d')
            start_date = (target_date - timedelta(days=60)).strftime('%Y-%m-%d')  # Get 60 days before for indicators
            end_date = target_date.strftime('%Y-%m-%d')
            
            # Try to get data from cache with correct signature
            market_data = self.cache.get_market_data(
                symbol=symbol, 
                start=start_date, 
                end=end_date, 
                source="polygon_consolidated"
            )
            
            if market_data is not None and len(market_data) >= 20:
                return market_data
            else:
                # Fallback: try to get broader date range
                start_date = "2024-01-01"
                end_date = "2024-12-31"
                market_data = self.cache.get_market_data(
                    symbol=symbol,
                    start=start_date,
                    end=end_date,
                    source="polygon_consolidated"
                )
                
                if market_data is not None and len(market_data) >= 20:
                    return market_data
                else:
                    logger.warning(f"Insufficient market data for {symbol} on {date}")
                    return None
                
        except Exception as e:
            logger.error(f"Error getting market data for {symbol} on {date}: {e}")
            return None
            
    def calculate_simple_macd(self, data: pd.DataFrame, fast=12, slow=26, signal=9) -> Dict[str, Any]:
        """
        Calculate MACD signal directly from price data.
        
        Args:
            data: DataFrame with OHLCV data
            fast, slow, signal: MACD parameters
            
        Returns:
            Dictionary with MACD signal information
        """
        try:
            if len(data) < slow + signal:
                return {
                    "action": "HOLD",
                    "strength": 0.0,
                    "confidence": 0.0,
                    "reasoning": "Insufficient data for MACD calculation"
                }
                
            # Calculate EMAs
            ema_fast = data['close'].ewm(span=fast).mean()
            ema_slow = data['close'].ewm(span=slow).mean()
            
            # MACD line
            macd_line = ema_fast - ema_slow
            
            # Signal line
            signal_line = macd_line.ewm(span=signal).mean()
            
            # MACD histogram (current - signal)
            histogram = macd_line - signal_line
            
            # Get latest values
            latest_histogram = histogram.iloc[-1]
            latest_macd = macd_line.iloc[-1]
            
            # Generate signal based on histogram
            if latest_histogram > 0.1:  # Positive histogram above threshold
                action = "BUY"
                strength = min(50.0, abs(latest_histogram) * 10)  # Scale to reasonable range
                confidence = 0.6
            elif latest_histogram < -0.1:  # Negative histogram below threshold
                action = "SELL"  
                strength = -min(50.0, abs(latest_histogram) * 10)
                confidence = 0.6
            else:
                action = "HOLD"
                strength = 0.0
                confidence = 0.3
                
            return {
                "action": action,
                "strength": strength,
                "confidence": confidence,
                "reasoning": f"MACD histogram: {latest_histogram:.4f}",
                "metadata": {
                    "macd_line": latest_macd,
                    "histogram": latest_histogram,
                    "parameters": f"{fast}/{slow}/{signal}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {
                "action": "HOLD",
                "strength": 0.0,
                "confidence": 0.0,
                "reasoning": f"MACD error: {str(e)}"
            }
            
    def collect_signals(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Collect signals from MACD and RSI.
        
        Args:
            symbol: Stock symbol
            date: Date for analysis
            
        Returns:
            Dictionary with both signals
        """
        signals = {
            "symbol": symbol,
            "date": date,
            "timestamp": datetime.now().isoformat(),
            "macd_signal": None,
            "rsi_signal": None,
            "error": None
        }
        
        try:
            # Get market data
            market_data = self.get_market_data(symbol, date)
            if market_data is None:
                signals["error"] = "No market data available"
                return signals
                
            # Calculate MACD signal
            macd_signal = self.calculate_simple_macd(market_data)
            signals["macd_signal"] = macd_signal
            
            # Calculate RSI signal
            rsi_signal = self.rsi_indicator.generate_signal(market_data)
            signals["rsi_signal"] = {
                "action": rsi_signal.action,
                "strength": rsi_signal.signal_strength,
                "confidence": rsi_signal.confidence,
                "reasoning": rsi_signal.reasoning,
                "metadata": rsi_signal.metadata
            }
            
        except Exception as e:
            logger.error(f"Error collecting signals: {e}")
            signals["error"] = str(e)
            
        return signals
        
    def make_decision(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make trading decision based on MACD + RSI voting.
        
        Args:
            signals: Collected signals from both indicators
            
        Returns:
            Final trading decision
        """
        decision = {
            "symbol": signals["symbol"],
            "date": signals["date"],
            "action": "HOLD",
            "confidence": 0.0,
            "position_size": 0.0,
            "reasoning": "No decision made",
            "signals_used": {},
            "error": signals.get("error")
        }
        
        if decision["error"]:
            return decision
            
        macd = signals["macd_signal"]
        rsi = signals["rsi_signal"]
        
        # Extract actions
        macd_action = macd["action"]
        rsi_action = rsi["action"]
        
        # Voting logic
        if macd_action == rsi_action and macd_action != "HOLD":
            # Both agree - strong signal
            decision["action"] = macd_action
            decision["confidence"] = min(0.85, (macd["confidence"] + rsi["confidence"]) / 2 + 0.15)
            decision["position_size"] = 1.0
            decision["reasoning"] = f"Strong consensus: Both MACD and RSI signal {macd_action}"
            
        elif (macd_action != "HOLD" and rsi_action == "HOLD") or (rsi_action != "HOLD" and macd_action == "HOLD"):
            # One signals, one neutral - weak signal  
            active_action = macd_action if macd_action != "HOLD" else rsi_action
            active_conf = macd["confidence"] if macd_action != "HOLD" else rsi["confidence"]
            
            decision["action"] = active_action
            decision["confidence"] = min(0.65, active_conf + 0.1)
            decision["position_size"] = 0.5
            decision["reasoning"] = f"Weak signal: Only {'MACD' if macd_action != 'HOLD' else 'RSI'} signals {active_action}"
            
        else:
            # Conflicting or both neutral
            decision["action"] = "HOLD"
            decision["confidence"] = 0.2
            decision["position_size"] = 0.0
            if macd_action != rsi_action and macd_action != "HOLD" and rsi_action != "HOLD":
                decision["reasoning"] = f"Conflicting signals: MACD={macd_action}, RSI={rsi_action}"
            else:
                decision["reasoning"] = "Both indicators neutral"
                
        # Store signal details for analysis
        decision["signals_used"] = {
            "macd": {
                "action": macd_action,
                "strength": macd["strength"],
                "confidence": macd["confidence"],
                "reasoning": macd["reasoning"]
            },
            "rsi": {
                "action": rsi_action,
                "strength": rsi["strength"], 
                "confidence": rsi["confidence"],
                "rsi_value": rsi["metadata"].get("rsi"),
                "reasoning": rsi["reasoning"]
            }
        }
        
        return decision
        
    def analyze_and_decide(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Full pipeline: get data → calculate signals → make decision.
        
        Args:
            symbol: Stock symbol
            date: Date for analysis
            
        Returns:
            Final decision with all details
        """
        # Collect signals
        signals = self.collect_signals(symbol, date)
        
        # Make decision
        decision = self.make_decision(signals)
        
        # Store in history
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "decision": decision
        })
        
        logger.info(f"Decision for {symbol} on {date}: {decision['action']} "
                   f"(conf: {decision['confidence']:.2f}, size: {decision['position_size']:.1f})")
        
        return decision
        
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of decisions made."""
        if not self.decision_history:
            return {"message": "No decisions made yet"}
            
        total = len(self.decision_history)
        actions = [h["decision"]["action"] for h in self.decision_history]
        
        buy_count = actions.count("BUY")
        sell_count = actions.count("SELL")
        hold_count = actions.count("HOLD")
        
        return {
            "total_decisions": total,
            "actions": {"BUY": buy_count, "SELL": sell_count, "HOLD": hold_count},
            "trading_signals": buy_count + sell_count,
            "trading_percentage": (buy_count + sell_count) / total * 100,
            "average_confidence": np.mean([h["decision"]["confidence"] for h in self.decision_history])
        }