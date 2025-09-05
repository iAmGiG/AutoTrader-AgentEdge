"""
Fibonacci-Enhanced Voting Orchestrator

Extends SimpleVotingOrchestrator with Fibonacci regime filtering.
Preserves the proven MACD + RSI voting while adding 34 EMA filter.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime

# Import base voting orchestrator
from .simple_voting_orchestrator import SimpleVotingOrchestrator
from .fibonacci_regime_module import FibonacciRegimeModule

logger = logging.getLogger(__name__)


class FibonacciEnhancedVoting(SimpleVotingOrchestrator):
    """
    Enhanced voting orchestrator with Fibonacci regime filtering.
    
    Inherits all functionality from SimpleVotingOrchestrator and adds:
    - 34 EMA filtering for signal validation
    - Market regime detection
    - Fibonacci confluence analysis
    """
    
    def __init__(self, config: Optional[Dict] = None, enable_fibonacci: bool = True):
        """
        Initialize enhanced voting orchestrator.
        
        Args:
            config: Configuration dictionary
            enable_fibonacci: Whether to enable Fibonacci filtering (default: True)
        """
        # Initialize base orchestrator
        super().__init__(config)
        
        # Add Fibonacci module
        self.enable_fibonacci = enable_fibonacci
        if self.enable_fibonacci:
            self.fibonacci_module = FibonacciRegimeModule(primary_period=34)
            logger.info("Fibonacci regime module enabled with 34 EMA filter")
        else:
            self.fibonacci_module = None
            logger.info("Running in baseline mode without Fibonacci filtering")
            
        # Track enhanced metrics
        self.filter_stats = {
            "total_signals": 0,
            "signals_passed": 0,
            "signals_blocked": 0,
            "regime_counts": {}
        }
        
    def make_decision(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make trading decision with optional Fibonacci filtering.
        
        Args:
            signals: Collected signals from indicators
            
        Returns:
            Final trading decision with Fibonacci enhancement
        """
        # Get base decision from parent class
        decision = super().make_decision(signals)
        
        # Apply Fibonacci filter if enabled
        if self.enable_fibonacci and self.fibonacci_module and decision["error"] is None:
            decision = self._apply_fibonacci_enhancement(decision, signals)
            
        return decision
        
    def _apply_fibonacci_enhancement(self, decision: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Fibonacci regime filtering to the voting decision.
        
        Args:
            decision: Base voting decision
            signals: Original signals with market data context
            
        Returns:
            Enhanced decision with Fibonacci filtering
        """
        try:
            # Get market data for the decision
            symbol = decision["symbol"]
            date = decision["date"]
            market_data = self.get_market_data(symbol, date)
            
            if market_data is None or len(market_data) < 34:
                decision["fibonacci_enhancement"] = "INSUFFICIENT_DATA"
                return decision
                
            # Apply EMA filter to the decision
            original_action = decision["action"]
            enhanced_decision = self.fibonacci_module.apply_ema_filter(
                market_data, 
                decision.copy()  # Pass a copy to preserve original
            )
            
            # Update decision with Fibonacci information
            decision["action"] = enhanced_decision["action"]
            decision["fibonacci_filter"] = enhanced_decision.get("fibonacci_filter", {})
            decision["market_regime"] = enhanced_decision.get("market_regime", "UNKNOWN")
            
            # Update filter statistics
            self.filter_stats["total_signals"] += 1
            if enhanced_decision["action"] == original_action:
                self.filter_stats["signals_passed"] += 1
            else:
                self.filter_stats["signals_blocked"] += 1
                
            # Track regime counts
            regime = enhanced_decision.get("market_regime", "UNKNOWN")
            self.filter_stats["regime_counts"][regime] = self.filter_stats["regime_counts"].get(regime, 0) + 1
            
            # Add confluence analysis for additional context
            confluence = self.fibonacci_module.analyze_fibonacci_confluence(market_data)
            decision["fibonacci_confluence"] = {
                "score": confluence.get("confluence_score", 0.0),
                "interpretation": confluence.get("interpretation", "UNKNOWN")
            }
            
            # Adjust position sizing based on regime (Phase 1 - conservative)
            if decision["action"] != "HOLD":
                decision = self._adjust_position_for_regime(decision)
                
        except Exception as e:
            logger.error(f"Error applying Fibonacci enhancement: {e}")
            decision["fibonacci_enhancement"] = f"ERROR: {str(e)}"
            
        return decision
        
    def _adjust_position_for_regime(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adjust position sizing based on detected market regime.
        
        Args:
            decision: Trading decision with regime information
            
        Returns:
            Decision with adjusted position sizing
        """
        regime = decision.get("market_regime", "UNKNOWN")
        original_size = decision.get("position_size", 1.0)
        
        # Conservative adjustments for Phase 1
        if regime == "STRONG_BULL" and decision["action"] == "BUY":
            # Increase position in strong bull regime for buys
            decision["position_size"] = min(1.2, original_size * 1.2)
            decision["reasoning"] += f" | Position increased for {regime} regime"
            
        elif regime == "STRONG_BEAR" and decision["action"] == "SELL":
            # Increase position in strong bear regime for sells
            decision["position_size"] = min(1.2, original_size * 1.2)
            decision["reasoning"] += f" | Position increased for {regime} regime"
            
        elif regime == "TRANSITIONAL":
            # Reduce position in transitional regime
            decision["position_size"] = original_size * 0.7
            decision["reasoning"] += f" | Position reduced for {regime} regime"
            
        elif regime in ["STRONG_BULL", "BULL"] and decision["action"] == "SELL":
            # Counter-trend in bull market - reduce position
            decision["position_size"] = original_size * 0.5
            decision["reasoning"] += f" | Counter-trend position reduced in {regime}"
            
        elif regime in ["STRONG_BEAR", "BEAR"] and decision["action"] == "BUY":
            # Counter-trend in bear market - reduce position
            decision["position_size"] = original_size * 0.5
            decision["reasoning"] += f" | Counter-trend position reduced in {regime}"
            
        return decision
        
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get enhanced performance summary including Fibonacci statistics.
        
        Returns:
            Performance summary with Fibonacci filter statistics
        """
        # Get base summary from parent
        summary = super().get_performance_summary()
        
        # Add Fibonacci filter statistics if enabled
        if self.enable_fibonacci:
            summary["fibonacci_filter"] = {
                "enabled": True,
                "total_signals": self.filter_stats["total_signals"],
                "signals_passed": self.filter_stats["signals_passed"],
                "signals_blocked": self.filter_stats["signals_blocked"],
                "filter_rate": (self.filter_stats["signals_blocked"] / max(1, self.filter_stats["total_signals"])) * 100,
                "regime_distribution": self.filter_stats["regime_counts"]
            }
            
            # Add regime statistics if available
            if self.fibonacci_module:
                summary["regime_statistics"] = self.fibonacci_module.get_regime_statistics()
        else:
            summary["fibonacci_filter"] = {"enabled": False}
            
        return summary
        
    def compare_with_baseline(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Compare Fibonacci-enhanced decision with baseline voting.
        
        Args:
            symbol: Stock symbol
            date: Date for analysis
            
        Returns:
            Comparison of baseline vs enhanced decisions
        """
        # Get baseline decision (disable Fibonacci temporarily)
        original_state = self.enable_fibonacci
        self.enable_fibonacci = False
        baseline_signals = self.collect_signals(symbol, date)
        baseline_decision = self.make_decision(baseline_signals)
        
        # Get enhanced decision
        self.enable_fibonacci = original_state
        enhanced_signals = self.collect_signals(symbol, date)
        enhanced_decision = self.make_decision(enhanced_signals)
        
        # Compare results
        comparison = {
            "symbol": symbol,
            "date": date,
            "baseline": {
                "action": baseline_decision["action"],
                "confidence": baseline_decision["confidence"],
                "position_size": baseline_decision["position_size"],
                "reasoning": baseline_decision["reasoning"]
            },
            "enhanced": {
                "action": enhanced_decision["action"],
                "confidence": enhanced_decision["confidence"],
                "position_size": enhanced_decision["position_size"],
                "reasoning": enhanced_decision["reasoning"],
                "regime": enhanced_decision.get("market_regime", "UNKNOWN"),
                "filter_status": enhanced_decision.get("fibonacci_filter", {}).get("status", "N/A")
            },
            "changes": {
                "action_changed": baseline_decision["action"] != enhanced_decision["action"],
                "confidence_delta": enhanced_decision["confidence"] - baseline_decision["confidence"],
                "position_delta": enhanced_decision["position_size"] - baseline_decision["position_size"]
            }
        }
        
        return comparison