#!/usr/bin/env python3
"""
Trading Orchestrator - Adapted from existing working MACD+RSI voting system
Standalone MACD+RSI voting logic with position tracking and risk management
"""

from typing import Dict, List, Any, Optional
import pandas as pd
import sys
import os
from datetime import datetime, timedelta
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.trading_tools.indicators import calculate_macd, calculate_rsi, calculate_voting_consensus
from src.trading_tools.data_fetch import MarketDataFetcher
from src.trading_tools.position_tracker import PositionTracker, Position
from src.trading_tools.risk_calculator import RiskCalculator
from config.trading_config import TradingConfig
from src.utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class TradingOrchestrator:
    """
    Standalone MACD+RSI voting orchestrator adapted from SimpleVotingOrchestrator.

    This maintains the VALIDATED MACD+RSI voting logic (0.856 Sharpe ratio)
    with position tracking, risk management, and multi-symbol scanning.
    """
    
    def __init__(self, initial_capital: float = 100000):
        self.config = TradingConfig()
        self.data_fetcher = MarketDataFetcher()
        self.position_tracker = PositionTracker(initial_capital=initial_capital)
        self.risk_calculator = RiskCalculator()
        
        # Decision tracking (adapted from legacy)
        self.decision_history = []
        self.monitored_symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "META"]

        logger.info("TradingOrchestrator initialized with MACD+RSI voting strategy")
    
    def get_market_data(self, symbol: str, date: str = None) -> Optional[pd.DataFrame]:
        """
        Adapted from legacy SimpleVotingOrchestrator.get_market_data()
        Get market data for MACD+RSI calculations.
        """
        try:
            if date is None:
                date = datetime.now().strftime('%Y-%m-%d')
            
            # Need 60+ days for reliable indicators
            target_date = datetime.strptime(date, '%Y-%m-%d')
            start_date = (target_date - timedelta(days=60)).strftime('%Y-%m-%d')
            
            # Try to get data using our data fetcher
            market_data = self.data_fetcher.get_price_data(symbol, days=60)
            
            if market_data is not None and len(market_data) >= 20:
                return market_data
            else:
                logger.warning(f"Insufficient market data for {symbol} on {date}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting market data for {symbol} on {date}: {e}")
            return None
    
    def calculate_macd_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Adapted from legacy calculate_simple_macd() with validated parameters.
        MACD(13/34/8) - Fibonacci parameters with 0.856 Sharpe validation.
        """
        try:
            if len(data) < 42:  # Need enough data for slow EMA + signal
                return {
                    "action": "HOLD",
                    "strength": 0.0,
                    "confidence": 0.0,
                    "reasoning": "Insufficient data for MACD calculation"
                }
            
            # Use our trading_tools calculator
            macd_config = self.config.get_macd_config()
            macd_data = calculate_macd(
                data['Close'] if 'Close' in data.columns else data['close'],
                fast=macd_config.fast_period,    # 13
                slow=macd_config.slow_period,    # 34  
                signal=macd_config.signal_period # 8
            )
            
            # Get latest histogram value
            latest_histogram = macd_data['histogram'].iloc[-1]
            
            # Generate signal based on histogram (validated logic)
            if latest_histogram > 0.1:  # Positive histogram above threshold
                action = "BUY"
                strength = min(50.0, abs(latest_histogram) * 10)
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
                    "macd_line": macd_data['macd'].iloc[-1],
                    "histogram": latest_histogram,
                    "parameters": f"MACD(13/34/8) - Fibonacci validated"
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
    
    def calculate_rsi_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate RSI signal using validated parameters RSI(14/30/70).
        """
        try:
            rsi_config = self.config.get_rsi_config()
            rsi_data = calculate_rsi(
                data['Close'] if 'Close' in data.columns else data['close'],
                period=rsi_config.period,
                oversold=rsi_config.oversold_threshold,
                overbought=rsi_config.overbought_threshold
            )
            
            current_rsi = rsi_data['rsi'].iloc[-1]
            
            # RSI signal logic (validated)
            if current_rsi < rsi_config.oversold_threshold:  # < 30
                action = "BUY"
                strength = (rsi_config.oversold_threshold - current_rsi) * 3.33
                confidence = 0.6
                reasoning = f"RSI oversold at {current_rsi:.1f}"
            elif current_rsi > rsi_config.overbought_threshold:  # > 70
                action = "SELL"
                strength = (current_rsi - rsi_config.overbought_threshold) * 3.33
                confidence = 0.6
                reasoning = f"RSI overbought at {current_rsi:.1f}"
            else:
                action = "HOLD"
                strength = 0.0
                confidence = 0.3
                reasoning = f"RSI neutral at {current_rsi:.1f}"
            
            return {
                "action": action,
                "strength": strength,
                "confidence": confidence,
                "reasoning": reasoning,
                "metadata": {
                    "rsi": current_rsi,
                    "oversold_threshold": rsi_config.oversold_threshold,
                    "overbought_threshold": rsi_config.overbought_threshold
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return {
                "action": "HOLD",
                "strength": 0.0,
                "confidence": 0.0,
                "reasoning": f"RSI error: {str(e)}"
            }
    
    def make_voting_decision(self, symbol: str, date: str = None) -> Dict[str, Any]:
        """
        Core MACD+RSI voting logic adapted from legacy make_decision().
        This is the VALIDATED logic that achieved 0.856 Sharpe ratio.
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
            
        decision = {
            "symbol": symbol,
            "date": date,
            "timestamp": datetime.now().isoformat(),
            "action": "HOLD",
            "confidence": 0.0,
            "position_size": 0.0,
            "reasoning": "No decision made",
            "signals_used": {},
            "error": None
        }
        
        try:
            # Get market data
            market_data = self.get_market_data(symbol, date)
            if market_data is None:
                decision["error"] = "No market data available"
                return decision
            
            # Calculate both signals
            macd_signal = self.calculate_macd_signal(market_data)
            rsi_signal = self.calculate_rsi_signal(market_data)
            
            # Extract actions
            macd_action = macd_signal["action"]
            rsi_action = rsi_signal["action"]
            
            # VALIDATED VOTING LOGIC (from legacy system)
            if macd_action == rsi_action and macd_action != "HOLD":
                # Both agree - strong signal
                decision["action"] = macd_action
                decision["confidence"] = min(0.85, (macd_signal["confidence"] + rsi_signal["confidence"]) / 2 + 0.15)
                decision["position_size"] = 1.0
                decision["reasoning"] = f"Strong consensus: Both MACD and RSI signal {macd_action}"
                
            elif (macd_action != "HOLD" and rsi_action == "HOLD") or (rsi_action != "HOLD" and macd_action == "HOLD"):
                # One signals, one neutral - weak signal
                active_action = macd_action if macd_action != "HOLD" else rsi_action
                active_conf = macd_signal["confidence"] if macd_action != "HOLD" else rsi_signal["confidence"]
                
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
            
            # Store signal details
            decision["signals_used"] = {
                "macd": macd_signal,
                "rsi": rsi_signal
            }
            
            # Store in history (adapted from legacy)
            self.decision_history.append({
                "timestamp": datetime.now().isoformat(),
                "decision": decision
            })
            
            logger.info(f"Decision for {symbol}: {decision['action']} "
                       f"(conf: {decision['confidence']:.2f}, size: {decision['position_size']:.1f})")
            
            return decision
            
        except Exception as e:
            logger.error(f"Error making decision for {symbol}: {e}")
            decision["error"] = str(e)
            return decision
    
    def scan_and_analyze(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        Scan multiple symbols and return analysis results.
        """
        if symbols is None:
            symbols = self.monitored_symbols
            
        results = {
            "timestamp": datetime.now().isoformat(),
            "symbols_scanned": len(symbols),
            "decisions": {},
            "summary": {
                "buy_signals": 0,
                "sell_signals": 0, 
                "hold_signals": 0,
                "errors": 0
            }
        }
        
        for symbol in symbols:
            try:
                decision = self.make_voting_decision(symbol)
                results["decisions"][symbol] = decision
                
                # Update summary
                if decision.get("error"):
                    results["summary"]["errors"] += 1
                elif decision["action"] == "BUY":
                    results["summary"]["buy_signals"] += 1
                elif decision["action"] == "SELL":
                    results["summary"]["sell_signals"] += 1
                else:
                    results["summary"]["hold_signals"] += 1
                    
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
                results["decisions"][symbol] = {"error": str(e)}
                results["summary"]["errors"] += 1
        
        return results
    
    def generate_human_readable_report(self, analysis_results: Dict[str, Any]) -> str:
        """
        Generate human-readable trading report.
        """
        report_parts = [
            "🤖 RH2MAS TRADING ANALYSIS",
            "=" * 50,
            f"Timestamp: {analysis_results['timestamp']}",
            f"Symbols Analyzed: {analysis_results['symbols_scanned']}",
            ""
        ]
        
        summary = analysis_results["summary"]
        report_parts.extend([
            "📊 SIGNAL SUMMARY:",
            f"   🟢 Buy Signals: {summary['buy_signals']}",
            f"   🔴 Sell Signals: {summary['sell_signals']}", 
            f"   ⚪ Hold/Neutral: {summary['hold_signals']}",
            f"   ❌ Errors: {summary['errors']}",
            ""
        ])
        
        # Individual symbol analysis
        report_parts.append("📈 INDIVIDUAL ANALYSIS:")
        report_parts.append("-" * 30)
        
        for symbol, decision in analysis_results["decisions"].items():
            if decision.get("error"):
                report_parts.append(f"❌ {symbol}: Error - {decision['error']}")
                continue
            
            action = decision["action"]
            confidence = decision["confidence"]
            
            emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(action, "❓")
            
            report_parts.extend([
                f"{emoji} {symbol}: {action} (conf: {confidence:.1%})",
                f"   Reasoning: {decision['reasoning']}",
                ""
            ])
        
        # Account status
        account_status = self.position_tracker.get_account_summary()
        report_parts.extend([
            "💰 ACCOUNT STATUS:",
            f"   Total Value: ${account_status.get('total_value', 0):,.2f}",
            f"   Available Cash: ${account_status.get('available_cash', 0):,.2f}",
            f"   Active Positions: {account_status.get('active_positions', 0)}",
        ])
        
        return "\n".join(report_parts)

def create_trading_orchestrator(initial_capital: float = 100000) -> TradingOrchestrator:
    """Factory function to create trading orchestrator."""
    return TradingOrchestrator(initial_capital=initial_capital)