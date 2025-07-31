"""Market Intelligence Agent - LLM-based market analysis and stock ranking.

This agent replaces rule-based market heat with comprehensive LLM analysis.
It searches current market conditions and ranks stocks based on investigation.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import json

from .base_agent import BaseAgent
from ..tools.tools import get_tools_for_agent, MARKET_INTELLIGENCE_AGENT

logger = logging.getLogger(__name__)


class MarketIntelligenceAgent(BaseAgent):
    """LLM-based agent that analyzes market conditions and ranks trading opportunities.
    
    Unlike the rule-based market heat calculation, this agent:
    - Uses LLM to search and investigate current market conditions
    - Considers multiple data sources and market factors
    - Provides intelligent ranking of stocks based on market regime
    - Explains reasoning for each assessment
    """
    
    def __init__(self, name: str = "MarketIntelligenceAgent", 
                 model_client=None, memory_system=None):
        # Get tools appropriate for market intelligence
        tools = get_tools_for_agent(MARKET_INTELLIGENCE_AGENT)
        
        # Initialize with enhanced system prompt
        super().__init__(
            name=name,
            tools=tools,
            memory_system=memory_system
        )
        
        # Store model_client as instance variable if provided
        if model_client:
            self.model_client = model_client
        
        self.config = {
            "system_prompt": """You are an expert Market Intelligence Agent responsible for analyzing 
current market conditions and ranking trading opportunities. Your role is to:

1. Search and investigate current market conditions comprehensively
2. Analyze macroeconomic factors, market sentiment, and risk indicators
3. Evaluate sector rotations and market regime
4. Rank stocks based on their attractiveness in the current market environment
5. Provide clear reasoning for your assessments

You have access to various market data tools. Use them to gather comprehensive information
about market conditions, not just single indicators like VXX. Consider:
- Overall market trends and momentum
- Sector performance and rotations
- Economic indicators and news
- Risk sentiment and volatility
- Correlation and market breadth

Always provide specific reasoning for your rankings and confidence levels.""",
            "temperature": 0.7,
            "max_tokens": 2000
        }
    
    async def analyze_market_and_rank_stocks(self, ta_signals: List[Dict], 
                                           date: str) -> Dict[str, Any]:
        """Analyze market conditions and rank stocks with TA signals.
        
        This is the key method that replaces mechanical market heat calculation.
        The LLM investigates market conditions and intelligently ranks opportunities.
        
        :param ta_signals: List of stocks with TA buy/sell signals
        :param date: Date for analysis
        :return: Ranked stocks with market analysis and reasoning
        """
        
        # Build comprehensive prompt for market analysis
        stocks_summary = "\n".join([
            f"- {sig['symbol']}: {sig['action']} signal, "
            f"MACD: {sig.get('macd_today', 'N/A')}, "
            f"Signal Strength: {sig.get('signal_strength', 'N/A')}"
            for sig in ta_signals
        ])
        
        prompt = f"""Analyze current market conditions for {date} and rank these stocks with technical signals:

Stocks with TA Signals:
{stocks_summary}

Tasks:
1. First, search and analyze current market conditions:
   - Use market data tools to check SPY, VIX/VXX levels
   - Analyze sector performance (XLK, XLF, XLE, etc.)
   - Search for recent market news and economic data
   - Assess overall market sentiment and risk appetite

2. Based on your market analysis, rank these stocks from 1 to {len(ta_signals)}:
   - Consider how each stock/sector fits the current market regime
   - Evaluate relative strength and momentum
   - Assess risk/reward in current conditions
   - Factor in any stock-specific news or events

3. For each stock, provide:
   - Rank (1 = most attractive)
   - Confidence score (0-1)
   - Brief reasoning connecting market conditions to this opportunity

Return a JSON object with:
{{
    "market_analysis": {{
        "overall_conditions": "description of current market state",
        "risk_sentiment": "current risk appetite assessment", 
        "key_factors": ["list of important market factors"],
        "regime": "market regime classification"
    }},
    "ranked_stocks": [
        {{
            "symbol": "SYMBOL",
            "rank": 1,
            "confidence": 0.85,
            "reasoning": "why this stock is attractive in current conditions",
            "market_alignment": "how it fits with market regime"
        }}
    ],
    "analysis_timestamp": "{datetime.now().isoformat()}"
}}"""
        
        try:
            # Use LLM with tools to analyze market and rank stocks
            response = await self.process_with_tools_async(
                prompt,
                self.config["system_prompt"],
                max_tokens=self.config["max_tokens"],
                temperature=self.config["temperature"]
            )
            
            # Parse response
            try:
                # Handle response that might have markdown formatting
                if "```json" in response:
                    json_start = response.find("```json") + 7
                    json_end = response.rfind("```")
                    response = response[json_start:json_end].strip()
                
                analysis = json.loads(response)
                
                # Add metadata
                analysis["agent"] = self.name
                analysis["date_analyzed"] = date
                analysis["ta_signals_count"] = len(ta_signals)
                
                logger.info(f"Market intelligence analysis complete for {date}")
                logger.info(f"Market regime: {analysis.get('market_analysis', {}).get('regime', 'Unknown')}")
                
                return analysis
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse market analysis response: {e}")
                logger.error(f"Raw response: {response}")
                
                # Return structured error response
                return {
                    "error": "Failed to parse analysis",
                    "raw_response": response,
                    "ranked_stocks": [
                        {
                            "symbol": sig["symbol"],
                            "rank": idx + 1,
                            "confidence": 0.5,
                            "reasoning": "Error in analysis - using default ranking"
                        }
                        for idx, sig in enumerate(ta_signals)
                    ]
                }
                
        except Exception as e:
            logger.error(f"Market intelligence analysis failed: {e}")
            return {
                "error": str(e),
                "ranked_stocks": []
            }
    
    def analyze_market_heat(self, date: str) -> float:
        """Legacy method for backward compatibility.
        
        Returns a simple heat score, but logs that the new method should be used.
        """
        logger.warning("analyze_market_heat called - use analyze_market_and_rank_stocks for full intelligence")
        
        # For compatibility, return neutral heat
        return 0.0
    
    def generate_reply(self, messages, context=None) -> str:
        """Generate a reply for chat-based interactions."""
        if not messages:
            return "No messages provided for analysis."
        
        # Extract the last user message
        last_message = messages[-1] if isinstance(messages, list) else str(messages)
        
        # Use the process_with_tools method for consistency
        return self.process_with_tools(
            last_message,
            self.config["system_prompt"]
        )