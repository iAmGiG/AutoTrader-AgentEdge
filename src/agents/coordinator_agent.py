"""Coordinator Agent module.

This agent coordinates the SentimentAgent and TechnicalAgent
and exposes an API to fetch combined signals.
"""

from typing import Any, Dict, Tuple, List
import json
import logging
from datetime import datetime

from .base_agent import BaseAgent
from .sentiment_agent import SentimentAgent  # Using enhanced version with VXX fallback
from .tech_agent import TechAgent
from .market_intelligence_agent import MarketIntelligenceAgent

logger = logging.getLogger(__name__)


class CoordinatorAgent(BaseAgent):
    """Agent that orchestrates SentimentAgent and TechnicalAgent."""

    def __init__(self, name: str = "CoordinatorAgent", memory_system: Any = None, 
                 use_llm_market_analysis: bool = False, model_client=None):
        super().__init__(name=name, tools=[], memory_system=memory_system)
        self.sentiment = SentimentAgent()
        self.technical = TechAgent()
        self.use_llm_market_analysis = use_llm_market_analysis
        
        # Initialize MarketIntelligenceAgent if using LLM analysis
        if self.use_llm_market_analysis:
            self.market_intelligence = MarketIntelligenceAgent(
                model_client=model_client,
                memory_system=memory_system
            )
            logger.info("CoordinatorAgent initialized with LLM-based market analysis")
        else:
            logger.info("CoordinatorAgent initialized with rule-based market heat")

    def generate_reply(self, messages, context=None):
        """Trivial implementation to satisfy BaseAgent abstract method."""
        return ""

    async def get_signals(self, date: str, symbol: str) -> Dict[str, Any]:
        """Return sentiment and technical signals for a symbol on a date."""
        signals, _ = await self.get_signals_with_reasoning(date, symbol)
        return signals

    async def get_signals_with_reasoning(self, date: str, symbol: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Return both extracted signals and raw LLM responses with full reasoning.

        Returns:
            tuple: (signals_dict, raw_responses_dict)
                - signals_dict: Processed signals with ok/error status
                - raw_responses_dict: Raw LLM responses including tool calls and full analysis
        """
        # More explicit prompts to trigger tool usage and return structured data
        sentiment_prompt = f"""Analyze market sentiment for {symbol} around {date}.

1. Use the fetch_all_news tool to get recent news about {symbol} 
2. Analyze the sentiment of the news articles
3. Provide your analysis including:
   - Key news themes and their sentiment impact
   - Overall sentiment score (-1 to 1)
   - Confidence level in your assessment
   - Any notable events or announcements

Return a JSON object with:
- 'score': average sentiment score (-1 to 1)
- 'analysis': your detailed sentiment analysis
- 'confidence': confidence level (0-1)
- 'key_themes': list of main themes found"""

        tech_prompt = f"""Perform technical analysis for {symbol} around {date}.

1. Use the fetch_market_data tool to get price data for {symbol}
2. Calculate MACD indicators
3. Analyze the technical patterns including:
   - MACD values and trends
   - Price action patterns
   - Volume analysis if available
   - Technical outlook

Return a JSON object with:
- 'macd_today': current MACD value
- 'macd_yest': previous MACD value
- 'analysis': your detailed technical analysis
- 'pattern': any identified patterns
- 'signal_strength': strength of technical signals"""

        try:
            # Build proper system prompts for each agent
            sentiment_system = getattr(self.sentiment, 'config', {}).get("system_prompt",
                                                                         "You are a sentiment analysis agent. Analyze news and market sentiment.")

            tech_system = "You are a technical analysis agent. Calculate technical indicators and provide MACD values."

            # Call sentiment agent using enhanced async method to get full response
            sentiment_resp, sentiment_full = await self._call_agent_with_full_response(
                self.sentiment,
                sentiment_prompt,
                sentiment_system
            )

            # Call technical agent using enhanced async method to get full response
            tech_resp, tech_full = await self._call_agent_with_full_response(
                self.technical,
                tech_prompt,
                tech_system
            )

            def _ensure_dict(val: Any) -> Dict[str, Any]:
                """Simple JSON parsing with error handling."""
                if isinstance(val, dict):
                    return val
                if isinstance(val, str):
                    # Remove markdown code blocks if present
                    val_clean = val.strip()
                    if val_clean.startswith("```json"):
                        val_clean = val_clean[7:]  # Remove ```json
                    elif val_clean.startswith("```"):
                        val_clean = val_clean[3:]  # Remove ```
                    if val_clean.endswith("```"):
                        val_clean = val_clean[:-3]  # Remove closing ```
                    val_clean = val_clean.strip()

                    # Try to find JSON object in the text
                    start_idx = val_clean.find('{')
                    end_idx = val_clean.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_str = val_clean[start_idx:end_idx + 1]
                        try:
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError as e:
                            print(f"JSON parsing failed: {e}")
                            print(f"Actual response: {val}")
                # Return empty dict on any parsing error
                return {}

            sentiment_dict = _ensure_dict(sentiment_resp)
            tech_dict = _ensure_dict(tech_resp)

            # Extract MACD values from technical response
            if "latest_row" in tech_dict:
                latest = tech_dict["latest_row"]
                if "MACD" in latest:
                    tech_dict["macd_today"] = latest["MACD"]
                if "MACD_prev" in latest:
                    tech_dict["macd_yest"] = latest["MACD_prev"]

            # Calculate market heat using either LLM or rule-based approach
            market_heat_data = {}
            if self.use_llm_market_analysis:
                # Use LLM-based market intelligence for more sophisticated analysis
                try:
                    # For single stock analysis, create a minimal TA signal
                    ta_signal = [{
                        "symbol": symbol,
                        "action": "potential",  # Will be refined by LLM
                        "macd_today": tech_dict.get("macd_today", "N/A"),
                        "signal_strength": tech_dict.get("signal_strength", 0.5)
                    }]
                    
                    market_analysis = await self.market_intelligence.analyze_market_and_rank_stocks(
                        ta_signals=ta_signal,
                        date=date
                    )
                    
                    # Extract market heat data from LLM analysis
                    market_heat_data = {
                        "heat_level": market_analysis.get("market_analysis", {}).get("heat_level", 0.0),
                        "interpretation": market_analysis.get("market_analysis", {}).get("overall_conditions", ""),
                        "regime": market_analysis.get("market_analysis", {}).get("regime", "Unknown"),
                        "key_factors": market_analysis.get("market_analysis", {}).get("key_factors", []),
                        "ranked_stocks": market_analysis.get("ranked_stocks", []),
                        "date": date,
                        "analysis_type": "llm"
                    }
                    logger.info(f"LLM Market analysis for {date}: {market_heat_data.get('regime', 'N/A')}")
                except Exception as e:
                    logger.error(f"Error in LLM market analysis: {e}")
                    # Fallback to rule-based on error
                    market_heat_data = self.sentiment.analyze_market_heat(date)
                    market_heat_data["analysis_type"] = "rule-based (fallback)"
            else:
                # Use traditional rule-based market heat calculation
                try:
                    market_heat_data = self.sentiment.analyze_market_heat(date)
                    market_heat_data["analysis_type"] = "rule-based"
                    logger.info(f"Rule-based market heat for {date}: {market_heat_data.get('heat_level', 'N/A')}")
                except Exception as e:
                    logger.error(f"Error calculating market heat: {e}")
                    market_heat_data = {
                        "heat_level": 0.0,
                        "interpretation": "Error calculating market heat",
                        "components": {},
                        "date": date,
                        "analysis_type": "error"
                    }

            # Prepare signals dictionary (same as before)
            signals = {"ok": True, "sentiment": sentiment_dict,
                       "technical": tech_dict, "market_heat": market_heat_data}

            # Prepare raw responses with full LLM reasoning
            raw_responses = {
                "timestamp": datetime.now().isoformat(),
                "date": date,
                "symbol": symbol,
                "sentiment": {
                    "raw_response": sentiment_full.get("response", sentiment_resp),
                    "tools_called": sentiment_full.get("tools_called", []),
                    "parsed_data": sentiment_dict,
                    "analysis": sentiment_dict.get("analysis", "No detailed analysis captured")
                },
                "technical": {
                    "raw_response": tech_full.get("response", tech_resp),
                    "tools_called": tech_full.get("tools_called", []),
                    "parsed_data": tech_dict,
                    "analysis": tech_dict.get("analysis", "No detailed analysis captured")
                },
                "market_heat": market_heat_data
            }

            return signals, raw_responses

        except Exception as e:
            error_response = {"ok": False, "error": str(e)}
            empty_raw = {
                "timestamp": datetime.now().isoformat(),
                "date": date,
                "symbol": symbol,
                "error": str(e)
            }
            return error_response, empty_raw

    async def _call_agent_with_full_response(self, agent: BaseAgent, prompt: str, system_prompt: str) -> Tuple[str, Dict[str, Any]]:
        """Call an agent and return both the processed response and full details.

        Returns:
            tuple: (processed_response, full_details)
                - processed_response: The extracted/processed response string
                - full_details: Dictionary with response, tools_called, etc.
        """
        # Store the original process_with_tools_async method response
        processed_response = await agent.process_with_tools_async(
            prompt,
            system_prompt
        )

        # For now, we'll create a structure for the full response
        # In a full implementation, we'd modify BaseAgent to expose more details
        full_details = {
            "response": processed_response,
            "tools_called": [],  # Would be populated from agent's tool call history
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent.name,
            "prompt": prompt,
            "system_prompt": system_prompt
        }

        # Note: To fully capture tool calls and intermediate reasoning,
        # we would need to enhance BaseAgent.process_with_tools_async
        # to return more detailed information about the LLM interaction

        return processed_response, full_details
    
    async def scan_and_rank_stocks(self, stock_list: List[str], date: str, 
                                   use_cache: bool = True) -> Dict[str, Any]:
        """Scan multiple stocks for TA signals and rank them using market intelligence.
        
        This method combines:
        1. Technical Agent's multi-stock scanning capability
        2. MarketIntelligenceAgent's LLM-based ranking (if enabled)
        3. Rule-based market heat calculation (as fallback)
        
        Args:
            stock_list: List of stock symbols to scan
            date: Date to analyze (YYYY-MM-DD format)
            use_cache: Whether to use cached market data
            
        Returns:
            Dictionary containing:
            - scan_results: Raw TA scan results
            - market_analysis: LLM market analysis (if enabled)
            - ranked_opportunities: Stocks ranked by attractiveness
            - market_heat: Overall market conditions
        """
        try:
            # Step 1: Use Technical Agent to scan all stocks
            logger.info(f"Scanning {len(stock_list)} stocks for TA signals on {date}")
            ta_scan_results = await self.technical.scan_stocks(stock_list, date, use_cache)
            
            # Extract stocks with entry signals
            ta_signals = []
            for entry in ta_scan_results.get("entries", []):
                ta_signals.append({
                    "symbol": entry["symbol"],
                    "action": "buy",
                    "macd_today": entry["histogram_value"],
                    "macd_prev": entry["histogram_prev"],
                    "signal_strength": entry["signal_strength"],
                    "price": entry["price"],
                    "change_pct": entry["change_pct"]
                })
            
            # Step 2: Rank opportunities using market intelligence or rules
            if self.use_llm_market_analysis and ta_signals:
                # Use LLM to analyze market and rank opportunities
                logger.info("Using LLM-based market intelligence for ranking")
                market_analysis = await self.market_intelligence.analyze_market_and_rank_stocks(
                    ta_signals=ta_signals,
                    date=date
                )
                
                # Extract ranked stocks from LLM analysis
                ranked_opportunities = market_analysis.get("ranked_stocks", [])
                market_heat_data = {
                    "heat_level": market_analysis.get("market_analysis", {}).get("heat_level", 0.0),
                    "regime": market_analysis.get("market_analysis", {}).get("regime", "Unknown"),
                    "interpretation": market_analysis.get("market_analysis", {}).get("overall_conditions", ""),
                    "key_factors": market_analysis.get("market_analysis", {}).get("key_factors", []),
                    "analysis_type": "llm"
                }
            else:
                # Use rule-based approach: rank by signal strength and filter by market heat
                logger.info("Using rule-based approach for ranking")
                
                # Get market heat
                market_heat_data = self.sentiment.analyze_market_heat(date)
                market_heat_data["analysis_type"] = "rule-based"
                
                # Simple ranking by signal strength
                ranked_opportunities = sorted(
                    ta_signals,
                    key=lambda x: x.get("signal_strength", 0),
                    reverse=True
                )
                
                # Add simple confidence based on market heat
                heat_level = market_heat_data.get("heat_level", 0.0)
                for i, opp in enumerate(ranked_opportunities):
                    # Higher confidence when market heat is positive
                    base_confidence = 0.7 - (i * 0.1)  # Decreasing confidence by rank
                    heat_adjustment = heat_level * 0.2  # +/- 20% based on heat
                    opp["rank"] = i + 1
                    opp["confidence"] = max(0.1, min(1.0, base_confidence + heat_adjustment))
                    opp["reasoning"] = f"Signal strength: {opp['signal_strength']:.2f}, Market heat: {heat_level:.2f}"
                    opp["market_alignment"] = "Favorable" if heat_level > 0 else "Challenging"
                
                market_analysis = {
                    "market_analysis": market_heat_data,
                    "ranked_stocks": ranked_opportunities
                }
            
            # Compile final results
            results = {
                "scan_date": date,
                "stocks_scanned": len(stock_list),
                "entries_found": len(ta_signals),
                "scan_results": ta_scan_results,
                "market_analysis": market_analysis if self.use_llm_market_analysis else None,
                "ranked_opportunities": ranked_opportunities,
                "market_heat": market_heat_data,
                "analysis_method": "llm" if self.use_llm_market_analysis else "rule-based"
            }
            
            logger.info(f"Scan complete: {len(ta_signals)} opportunities found and ranked")
            return results
            
        except Exception as e:
            logger.error(f"Error in scan_and_rank_stocks: {e}")
            return {
                "error": str(e),
                "scan_date": date,
                "stocks_scanned": len(stock_list),
                "entries_found": 0,
                "ranked_opportunities": []
            }
