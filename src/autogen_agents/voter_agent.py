#!/usr/bin/env python3
"""
Voter Agent - MACD+RSI voting functionality
Properly implemented using base_agent.py from legacy system
"""

import sys
import os
from typing import Dict, Any, List
import pandas as pd
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from .base_agent import BaseAgent
from src.trading_tools.indicators import calculate_macd, calculate_rsi
from config.trading_config import TradingConfig

logger = logging.getLogger(__name__)

class VoterAgent(BaseAgent):
    """
    Trading decision agent that evaluates signals using validated MACD+RSI voting.
    Inherits from BaseAgent which provides proper autogen-agentchat framework.
    """
    
    def __init__(self, name="voter_agent", **kwargs):
        super().__init__(name=name, **kwargs)
        self.config = TradingConfig()
        logger.info(f"VoterAgent '{name}' initialized with MACD+RSI voting")
    
    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen's required method for handling incoming messages.
        Processes MACD+RSI voting requests.
        """
        if not messages:
            return "No messages to process."
        
        # Get the latest message
        latest_message = messages[-1]
        if hasattr(latest_message, 'content'):
            content = latest_message.content
        else:
            content = str(latest_message)
        
        # Use the base agent's tool processing capability
        system_prompt = """You are a trading decision agent using validated MACD+RSI voting.

Your role:
1. Analyze MACD(13/34/8) and RSI(14/30/70) signals
2. Apply consensus voting: both indicators must agree for entry
3. Provide clear trading recommendations with confidence levels

Key principles:
- MACD(13/34/8): Use Fibonacci parameters validated for 0.856 Sharpe
- RSI(14/30/70): Standard oversold/overbought levels
- Consensus required: Both bullish = BUY, Both bearish = SELL, Mixed = HOLD
- Include confidence levels and technical reasoning"""

        try:
            return self.process_with_tools(content, system_prompt)
        except Exception as e:
            logger.error(f"VoterAgent error: {e}")
            return f"Error processing trading decision: {str(e)}"
    
    def evaluate_macd_rsi_consensus(self, symbol: str, price_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Core MACD+RSI voting method adapted from legacy system.
        This preserves the validated logic that achieved 0.856 Sharpe.
        """
        try:
            if len(price_data) < 42:  # Need enough data for indicators
                return {
                    "action": "HOLD",
                    "confidence": 0.0,
                    "reasoning": "Insufficient data for reliable signals"
                }
            
            # Calculate indicators using validated parameters
            macd_config = self.config.get_macd_config()
            rsi_config = self.config.get_rsi_config()
            
            # MACD calculation
            prices = price_data['Close'] if 'Close' in price_data.columns else price_data['close']
            macd_data = calculate_macd(
                prices,
                fast=macd_config.fast_period,      # 13
                slow=macd_config.slow_period,      # 34
                signal=macd_config.signal_period   # 8
            )
            
            # RSI calculation
            rsi_data = calculate_rsi(
                prices,
                period=rsi_config.period,                    # 14
                oversold=rsi_config.oversold_threshold,      # 30
                overbought=rsi_config.overbought_threshold   # 70
            )
            
            # MACD signal (based on histogram)
            latest_histogram = macd_data['histogram'].iloc[-1]
            if latest_histogram > 0.1:
                macd_action = "BUY"
                macd_conf = 0.6
            elif latest_histogram < -0.1:
                macd_action = "SELL"
                macd_conf = 0.6
            else:
                macd_action = "HOLD"
                macd_conf = 0.3
            
            # RSI signal
            current_rsi = rsi_data['rsi'].iloc[-1]
            if current_rsi < rsi_config.oversold_threshold:
                rsi_action = "BUY"
                rsi_conf = 0.6
            elif current_rsi > rsi_config.overbought_threshold:
                rsi_action = "SELL"
                rsi_conf = 0.6
            else:
                rsi_action = "HOLD"
                rsi_conf = 0.3
            
            # VALIDATED VOTING LOGIC (from legacy system achieving 0.856 Sharpe)
            if macd_action == rsi_action and macd_action != "HOLD":
                # Both agree - strong signal
                action = macd_action
                confidence = min(0.85, (macd_conf + rsi_conf) / 2 + 0.15)
                position_size = 1.0
                reasoning = f"Strong consensus: Both MACD and RSI signal {action}"
                
            elif (macd_action != "HOLD" and rsi_action == "HOLD") or (rsi_action != "HOLD" and macd_action == "HOLD"):
                # One signals, one neutral - weak signal
                active_action = macd_action if macd_action != "HOLD" else rsi_action
                active_conf = macd_conf if macd_action != "HOLD" else rsi_conf
                
                action = active_action
                confidence = min(0.65, active_conf + 0.1)
                position_size = 0.5
                reasoning = f"Weak signal: Only {'MACD' if macd_action != 'HOLD' else 'RSI'} signals {active_action}"
                
            else:
                # Conflicting or both neutral
                action = "HOLD"
                confidence = 0.2
                position_size = 0.0
                if macd_action != rsi_action and macd_action != "HOLD" and rsi_action != "HOLD":
                    reasoning = f"Conflicting signals: MACD={macd_action}, RSI={rsi_action}"
                else:
                    reasoning = "Both indicators neutral"
            
            return {
                "symbol": symbol,
                "action": action,
                "confidence": confidence,
                "position_size": position_size,
                "reasoning": reasoning,
                "technical_details": {
                    "macd_action": macd_action,
                    "rsi_action": rsi_action,
                    "macd_histogram": latest_histogram,
                    "rsi_value": current_rsi,
                    "current_price": prices.iloc[-1]
                }
            }
            
        except Exception as e:
            logger.error(f"Error in MACD+RSI consensus: {e}")
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Analysis error: {str(e)}"
            }

def create_voter_agent(name="voter_agent") -> VoterAgent:
    """Factory function to create a properly configured voter agent."""
    return VoterAgent(name=name)