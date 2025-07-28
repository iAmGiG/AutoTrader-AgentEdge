"""LLM Strategy Agent - Makes trading decisions using LLM reasoning, not mechanical rules.

This agent demonstrates the power of LLM-based decision making vs rule-based systems.
"""

import logging
from typing import Dict, Optional, List, Any
import json
from datetime import datetime

from .base_agent import BaseAgent
from .market_intelligence_agent import MarketIntelligenceAgent

logger = logging.getLogger(__name__)


class LLMStrategyAgent(BaseAgent):
    """Strategy agent that uses LLM for actual trading decisions.
    
    Unlike the mechanical StrategyAgent, this agent:
    - Uses LLM to reason about trading decisions
    - Considers market intelligence rankings
    - Provides detailed explanations for each decision
    - Adapts to changing market conditions
    """
    
    def __init__(self, name: str = "LLMStrategyAgent", 
                 model_client=None, memory_system=None):
        # LLM strategy agent doesn't need tools - it reasons about provided data
        super().__init__(
            name=name,
            tools=[],
            memory_system=memory_system
        )
        
        # Store model_client as instance variable if provided
        if model_client:
            self.model_client = model_client
        
        self.position = 0  # 0 = flat, 1 = long
        self.entry_price = None
        self.entry_date = None
        self.trade_log = []
        self.trades = []
        self.decision_history = []  # Track LLM reasoning
        
        self.config = {
            "system_prompt": """You are an expert trading strategist making real trading decisions.
Your goal is to maximize risk-adjusted returns by making intelligent BUY/SELL/HOLD decisions.

Key principles:
1. Consider ALL available information: technical signals, sentiment, market conditions
2. Think about risk/reward, not just directional moves
3. Factor in market regime and correlations
4. Be decisive but prudent - don't overtrade
5. Always explain your reasoning clearly

Current position tracking:
- You will be told if you're currently FLAT (no position) or LONG (holding stock)
- If FLAT, you can only BUY or HOLD
- If LONG, you can only SELL or HOLD
- Track your entry price and consider it in exit decisions""",
            "temperature": 0.3,  # Lower temperature for more consistent decisions
            "max_tokens": 1500
        }
    
    async def decide_trade_llm(self, aggregated: Dict, price: float, trade_date: str) -> Dict:
        """Make trading decision using LLM reasoning.
        
        :param aggregated: Signals from all agents (sentiment, technical, market_heat)
        :param price: Current stock price
        :param trade_date: Date of trading decision
        :return: Trading decision with detailed reasoning
        """
        
        # Extract key data
        sentiment = aggregated.get("sentiment", {})
        technical = aggregated.get("technical", {})
        market_heat = aggregated.get("market_heat", {})
        
        # Build comprehensive context for LLM
        position_status = "FLAT (no position)" if self.position == 0 else f"LONG (entry @ ${self.entry_price:.2f})"
        current_pnl = ((price - self.entry_price) / self.entry_price * 100) if self.position == 1 and self.entry_price else 0
        
        prompt = f"""Make a trading decision for {aggregated.get('symbol', 'UNKNOWN')} on {trade_date}.

Current Status:
- Position: {position_status}
- Current Price: ${price:.2f}
{"- Current P&L: " + f"{current_pnl:+.2f}%" if self.position == 1 else ""}

Technical Analysis:
- MACD Today: {technical.get('macd_today', 'N/A')}
- MACD Yesterday: {technical.get('macd_yest', 'N/A')}
- Technical Analysis: {technical.get('analysis', 'No analysis available')}
- Signal Strength: {technical.get('signal_strength', 'N/A')}

Sentiment Analysis:
- Sentiment Score: {sentiment.get('score', 'N/A')} (-1 to +1 scale)
- Key Themes: {sentiment.get('key_themes', [])}
- Confidence: {sentiment.get('confidence', 'N/A')}
- Analysis: {sentiment.get('analysis', 'No analysis available')}

Market Conditions:
- Market Heat Level: {market_heat.get('heat_level', 'N/A')} (-1 to +1 scale)
- Interpretation: {market_heat.get('interpretation', 'No data')}
- VXX Component: {market_heat.get('components', {}).get('vxx', {}).get('score', 'N/A')}
- SPY Momentum: {market_heat.get('components', {}).get('spy_momentum', {}).get('score', 'N/A')}
- Sector Rotation: {market_heat.get('components', {}).get('sector_rotation', {}).get('score', 'N/A')}

Based on all this information, decide whether to BUY, SELL, or HOLD.

Return a JSON object with:
{{
    "action": "BUY/SELL/HOLD",
    "confidence": 0.0-1.0,
    "reasoning": {{
        "primary_factors": ["list key factors driving decision"],
        "risk_assessment": "evaluation of risks",
        "market_context": "how market conditions affect decision",
        "technical_view": "interpretation of technical signals",
        "sentiment_impact": "how sentiment influences decision",
        "decision_rationale": "clear explanation of why this action now"
    }},
    "risk_level": "low/medium/high",
    "expected_horizon": "expected holding period if buying",
    "stop_loss_consideration": "where you might exit if wrong"
}}"""
        
        try:
            # Get LLM decision
            response = await self.process_with_tools_async(
                prompt,
                self.config["system_prompt"],
                max_tokens=self.config["max_tokens"],
                temperature=self.config["temperature"]
            )
            
            # Parse response
            try:
                if "```json" in response:
                    json_start = response.find("```json") + 7
                    json_end = response.rfind("```")
                    response = response[json_start:json_end].strip()
                
                decision = json.loads(response)
                
                # Validate and execute decision
                action = decision.get("action", "HOLD").upper()
                
                # Ensure valid action based on position
                if self.position == 0 and action == "SELL":
                    action = "HOLD"
                    decision["action"] = "HOLD"
                    decision["reasoning"]["decision_rationale"] = "Cannot SELL when flat - adjusted to HOLD"
                elif self.position == 1 and action == "BUY":
                    action = "HOLD"  
                    decision["action"] = "HOLD"
                    decision["reasoning"]["decision_rationale"] = "Already long - adjusted to HOLD"
                
                # Execute trade
                if action == "BUY" and self.position == 0:
                    self.position = 1
                    self.entry_price = price
                    self.entry_date = trade_date
                elif action == "SELL" and self.position == 1:
                    self.position = 0
                    # Record completed trade
                    if self.entry_price:
                        self.trades.append({
                            "entry_date": self.entry_date,
                            "exit_date": trade_date,
                            "entry_price": self.entry_price,
                            "exit_price": price,
                            "return": (price - self.entry_price) / self.entry_price,
                            "profit": price - self.entry_price,
                            "reasoning_entry": self.get_entry_reasoning(),
                            "reasoning_exit": decision.get("reasoning", {})
                        })
                        self.entry_price = None
                        self.entry_date = None
                
                # Store decision with full context
                self.decision_history.append({
                    "date": trade_date,
                    "action": action,
                    "price": price,
                    "decision": decision,
                    "aggregated_signals": aggregated
                })
                
                # Log decision
                logger.info(f"LLM Decision for {trade_date}: {action} "
                           f"(confidence: {decision.get('confidence', 'N/A')})")
                logger.info(f"Rationale: {decision.get('reasoning', {}).get('decision_rationale', 'No rationale')}")
                
                return {
                    "action": action,
                    "qty": 100 if action == "BUY" else 0,
                    "confidence": decision.get("confidence", 0.5),
                    "reasoning": decision.get("reasoning", {}),
                    "risk_level": decision.get("risk_level", "medium"),
                    "llm_based": True  # Flag to indicate LLM decision
                }
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM decision: {e}")
                logger.error(f"Raw response: {response}")
                
                return {
                    "action": "HOLD",
                    "qty": 0,
                    "reasoning": {"error": "Failed to parse LLM response"},
                    "llm_based": True,
                    "raw_response": response
                }
                
        except Exception as e:
            logger.error(f"LLM decision failed: {e}")
            return {
                "action": "HOLD",
                "qty": 0,
                "reasoning": {"error": str(e)},
                "llm_based": True
            }
    
    def get_entry_reasoning(self) -> Dict:
        """Get reasoning for the entry that led to current position."""
        # Find the decision that opened the current position
        for decision in reversed(self.decision_history):
            if decision["action"] == "BUY":
                return decision.get("decision", {}).get("reasoning", {})
        return {}
    
    def get_metrics(self, initial_capital: float = 10000, risk_free_rate: float = 0.02) -> Dict:
        """Calculate performance metrics (same as mechanical version for comparison)."""
        if not self.trades:
            return {
                "total_return": 0.0,
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "num_trades": 0,
                "expectancy": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_confidence": 0.0,
                "decision_quality": 0.0
            }
        
        # Standard metrics calculation
        profits = [t["profit"] for t in self.trades]
        returns = [t["return"] for t in self.trades]
        
        winning_trades = [t for t in self.trades if t["profit"] > 0]
        losing_trades = [t for t in self.trades if t["profit"] <= 0]
        
        total_return = sum(profits) / initial_capital
        win_rate = len(winning_trades) / len(self.trades)
        avg_win = sum(t["profit"] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(abs(t["profit"]) for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # LLM-specific metrics
        confidences = [d["decision"].get("confidence", 0.5) for d in self.decision_history if "decision" in d]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Decision quality based on outcome alignment with confidence
        decision_quality_scores = []
        for trade in self.trades:
            # Find the entry decision for this trade
            entry_confidence = 0.5
            for decision in self.decision_history:
                if decision["date"] == trade["entry_date"] and decision["action"] == "BUY":
                    entry_confidence = decision["decision"].get("confidence", 0.5)
                    break
            
            # Quality = confidence if profitable, (1-confidence) if loss
            if trade["profit"] > 0:
                decision_quality_scores.append(entry_confidence)
            else:
                decision_quality_scores.append(1 - entry_confidence)
        
        decision_quality = sum(decision_quality_scores) / len(decision_quality_scores) if decision_quality_scores else 0.5
        
        return {
            "total_return": total_return,
            "total_return_pct": total_return * 100,
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": (sum(t["profit"] for t in winning_trades) / 
                            sum(abs(t["profit"]) for t in losing_trades)) if losing_trades else float('inf'),
            "sharpe_ratio": (sum(returns) / len(returns)) / (sum((r - sum(returns)/len(returns))**2 for r in returns) / len(returns))**0.5 if len(returns) > 1 else 0,
            "max_drawdown": self._calculate_max_drawdown(profits),
            "num_trades": len(self.trades),
            "expectancy": (win_rate * avg_win) - ((1 - win_rate) * avg_loss),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "avg_confidence": avg_confidence,
            "decision_quality": decision_quality
        }
    
    def _calculate_max_drawdown(self, profits: List[float]) -> float:
        """Calculate maximum drawdown from profit series."""
        if not profits:
            return 0.0
        
        cumulative = []
        total = 0
        for p in profits:
            total += p
            cumulative.append(total)
        
        peak = cumulative[0]
        max_dd = 0
        for value in cumulative:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def decide_trade(self, aggregated: Dict, price: float, trade_date: str) -> Dict:
        """Synchronous wrapper for backtesting compatibility."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.decide_trade_llm(aggregated, price, trade_date)
            )
        finally:
            loop.close()
    
    def generate_reply(self, messages, context=None) -> str:
        """Required by BaseAgent but not used for trading."""
        return "LLMStrategyAgent makes trading decisions via decide_trade_llm method"