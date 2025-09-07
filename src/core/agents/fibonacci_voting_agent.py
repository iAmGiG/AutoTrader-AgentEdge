"""
Fibonacci-Enhanced Voting Agent - GitHub Issue #297 Phase 2 Ready

Modular enhancement framework for baseline MACD+RSI voting.
Phase 1 (EMA34 filter): Tested, no improvement, archived
Phase 2 (CCI filters): Ready for implementation
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from datetime import datetime

# Import base voting orchestrator
from .macd_rsi_voting_agent import SimpleVotingOrchestrator

logger = logging.getLogger(__name__)


class FibonacciEnhancedVoting(SimpleVotingOrchestrator):
    """
    Phase 1 Fibonacci Enhancement per GitHub Issue #297.
    
    Adds 34 EMA filter to baseline MACD(13/34/8) + RSI voting.
    Keeps modular architecture for future Phase 2-4 additions.
    """
    
    def __init__(self, config: Optional[Dict] = None, enable_ema34_filter: bool = True):
        """
        Initialize Phase 1 enhanced voting agent.
        
        Args:
            config: Configuration dictionary
            enable_ema34_filter: Whether to enable 34 EMA filter (default: True)
        """
        # Initialize baseline orchestrator (13/34/8 MACD + RSI)
        super().__init__(config)
        
        # Phase 1 configuration
        self.enable_ema34_filter = enable_ema34_filter
        
        # Track Phase 1 statistics
        self.filter_stats = {
            "total_signals": 0,
            "signals_passed": 0,
            "signals_blocked": 0,
            "buy_signals_blocked": 0,
            "sell_signals_blocked": 0
        }
        
        logger.info(f"Phase 1 Fibonacci Enhanced Voting initialized (EMA34 filter: {enable_ema34_filter})")
        
    def make_decision(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make trading decision with Phase 1 enhancement.
        
        Args:
            signals: Collected signals from MACD and RSI
            
        Returns:
            Final decision with optional 34 EMA filtering
        """
        # Get baseline decision from parent (MACD 13/34/8 + RSI voting)
        decision = super().make_decision(signals)
        
        # Apply Phase 1 enhancement if enabled and no errors
        if self.enable_ema34_filter and decision["error"] is None:
            decision = self._apply_phase1_filter(decision, signals)
            
        return decision
        
    def _apply_phase1_filter(self, decision: Dict[str, Any], signals: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Phase 1: 34 EMA filter per GitHub issue #297.
        
        Args:
            decision: Baseline voting decision
            signals: Original signals with market data access
            
        Returns:
            Decision with Phase 1 filtering applied
        """
        try:
            # Get market data for EMA34 calculation
            symbol = decision["symbol"]
            date = decision["date"]
            market_data = self.get_market_data(symbol, date)
            
            if market_data is None or len(market_data) < 34:
                decision["phase1_filter"] = "INSUFFICIENT_DATA"
                return decision
                
            # Apply 34 EMA filter to the baseline decision
            original_action = decision["action"]
            enhanced_decision = self.apply_ema34_filter(market_data, decision)
            
            # Update filter statistics
            self.filter_stats["total_signals"] += 1
            if enhanced_decision["action"] == original_action:
                self.filter_stats["signals_passed"] += 1
            else:
                self.filter_stats["signals_blocked"] += 1
                if original_action == "BUY":
                    self.filter_stats["buy_signals_blocked"] += 1
                elif original_action == "SELL":
                    self.filter_stats["sell_signals_blocked"] += 1
                    
            # Mark as Phase 1 enhanced
            enhanced_decision["phase1_enhanced"] = True
            enhanced_decision["baseline_action"] = original_action
            
            return enhanced_decision
            
        except Exception as e:
            logger.error(f"Error applying Phase 1 filter: {e}")
            decision["phase1_filter"] = f"ERROR: {str(e)}"
            return decision
            
    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get Phase 1 performance summary with filter statistics.
        
        Returns:
            Enhanced summary with Phase 1 filter metrics
        """
        # Get baseline summary
        summary = super().get_performance_summary()
        
        # Add Phase 1 statistics
        if self.enable_ema34_filter:
            total = max(1, self.filter_stats["total_signals"])
            summary["phase1_filter"] = {
                "enabled": True,
                "total_signals": self.filter_stats["total_signals"],
                "signals_passed": self.filter_stats["signals_passed"],
                "signals_blocked": self.filter_stats["signals_blocked"],
                "filter_rate": (self.filter_stats["signals_blocked"] / total) * 100,
                "buy_blocks": self.filter_stats["buy_signals_blocked"],
                "sell_blocks": self.filter_stats["sell_signals_blocked"]
            }
        else:
            summary["phase1_filter"] = {"enabled": False}
            
        return summary
        
    def compare_baseline_vs_phase1(self, symbol: str, date: str) -> Dict[str, Any]:
        """
        Compare baseline decision vs Phase 1 enhanced decision.
        
        Args:
            symbol: Stock symbol
            date: Date for analysis
            
        Returns:
            Comparison of baseline vs Phase 1 enhanced
        """
        # Get baseline decision (disable filter temporarily)
        original_state = self.enable_ema34_filter
        self.enable_ema34_filter = False
        baseline_signals = self.collect_signals(symbol, date)
        baseline_decision = self.make_decision(baseline_signals)
        
        # Get Phase 1 enhanced decision
        self.enable_ema34_filter = original_state
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
            "phase1_enhanced": {
                "action": enhanced_decision["action"],
                "confidence": enhanced_decision["confidence"],
                "position_size": enhanced_decision["position_size"],
                "reasoning": enhanced_decision["reasoning"],
                "filter_status": enhanced_decision.get("ema34_filter", {}).get("price_vs_ema34", "N/A")
            },
            "changes": {
                "action_changed": baseline_decision["action"] != enhanced_decision["action"],
                "filter_blocked": baseline_decision["action"] != "HOLD" and enhanced_decision["action"] == "HOLD",
                "confidence_delta": enhanced_decision["confidence"] - baseline_decision["confidence"]
            }
        }
        
        return comparison