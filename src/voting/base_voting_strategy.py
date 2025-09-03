"""
Base Voting Strategy for Multi-Indicator Ensemble Trading System

Implements the foundation for transforming single MACD strategy to ensemble voting.
Builds on existing V0-V4 sentiment framework patterns using AutoGen AgentChat.

Key Features:
- Indicator signal collection and aggregation
- Confidence-weighted voting mechanism  
- Market regime awareness
- Integration with existing TechAgent and sentiment agents
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

import pandas as pd

from src.agents.base_agent import BaseAgent
from src.tools.tools import STRATEGY_AGENT, get_tools_for_agent

logger = logging.getLogger(__name__)

class SignalStrength(Enum):
    """Signal strength levels for granular voting"""
    VERY_BEARISH = -100
    BEARISH = -50
    WEAK_BEARISH = -25
    NEUTRAL = 0
    WEAK_BULLISH = 25
    BULLISH = 50
    VERY_BULLISH = 100

class MarketRegime(Enum):
    """Market regime types for adaptive weighting"""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"

@dataclass
class IndicatorSignal:
    """Individual indicator signal with confidence"""
    indicator_name: str
    signal_strength: int  # -100 to +100
    confidence: float  # 0.0 to 1.0
    raw_value: float
    timestamp: str
    
class VotingDecision:
    """Final voting decision with detailed breakdown"""
    def __init__(self):
        self.action: Optional[str] = None  # 'BUY', 'SELL', 'HOLD'
        self.confidence: float = 0.0
        self.vote_breakdown: Dict[str, IndicatorSignal] = {}
        self.weighted_score: float = 0.0
        self.market_regime: Optional[MarketRegime] = None
        self.reasoning: str = ""

class BaseVotingStrategy(BaseAgent, ABC):
    """
    Base class for multi-indicator voting strategies.
    
    Provides core voting framework that can be extended for specific
    voting implementations (basic, weighted, regime-adaptive).
    
    Integrates with existing V0-V4 sentiment agents as additional indicators.
    """
    
    def __init__(self, name: str = "BaseVotingStrategy", memory_system=None):
        """Initialize base voting strategy with minimal LLM config"""
        
        # Minimal LLM config for orchestration only
        voting_llm_config = {
            "temperature": 0.1,  # Low temperature for consistent decisions
            "max_tokens": 2048,  # Sufficient for reasoning
            "model": "gpt-4o-mini"  # Cost-effective for voting logic
        }
        
        # Get strategy agent tools (aggregation focused)
        tools = get_tools_for_agent(STRATEGY_AGENT)
        
        super().__init__(
            name=name,
            tools=tools,
            memory_system=memory_system,
            llm_config=voting_llm_config
        )
        
        self.logger = logger
        
        # Voting configuration
        self.indicators = {}  # Will be populated by subclasses
        self.indicator_weights = {}  # Confidence-based weights
        self.market_regime_weights = {}  # Regime-specific adjustments
        
        # Performance tracking
        self.decision_history = []
        self.indicator_performance = {}
        
        # Integration points for existing agents
        self.tech_agent = None  # Will be injected for MACD signals
        self.sentiment_agents = {}  # Will be injected for V0-V4 sentiment
        
    def register_tech_agent(self, tech_agent):
        """Register existing TechAgent for MACD signals"""
        self.tech_agent = tech_agent
        logger.info(f"Registered TechAgent: {tech_agent.name}")
        
    def register_sentiment_agent(self, version: str, agent):
        """Register V0-V4 sentiment agents as indicators"""
        self.sentiment_agents[version] = agent
        logger.info(f"Registered sentiment agent V{version}: {agent.name}")
        
    # ==================== Core Voting Methods ====================
        
    @abstractmethod
    def calculate_indicator_signals(
        self, symbol: str, date: str, market_data: Dict[str, Any]
    ) -> Dict[str, IndicatorSignal]:
        """
        Calculate all indicator signals for voting.
        Must be implemented by subclasses.
        
        Args:
            symbol: Stock symbol
            date: Trading date
            market_data: Market data context
            
        Returns:
            Dictionary of indicator signals
        """
        pass
    
    @abstractmethod  
    def determine_market_regime(self, market_data: Dict[str, Any]) -> MarketRegime:
        """
        Determine current market regime for adaptive weighting.
        Must be implemented by subclasses.
        
        Args:
            market_data: Market data context
            
        Returns:
            Current market regime
        """
        pass
    
    @abstractmethod
    def calculate_weighted_vote(
        self, signals: Dict[str, IndicatorSignal], regime: MarketRegime
    ) -> VotingDecision:
        """
        Calculate final weighted voting decision.
        Must be implemented by subclasses.
        
        Args:
            signals: Dictionary of indicator signals
            regime: Current market regime
            
        Returns:
            Final voting decision
        """
        pass
    
    # ==================== Integration Methods ====================
    
    def get_macd_signal(self, symbol: str, date: str) -> Optional[IndicatorSignal]:
        """Get MACD signal from existing TechAgent"""
        if not self.tech_agent:
            logger.warning("No TechAgent registered for MACD signals")
            return None
            
        try:
            # Use existing TechAgent pattern for MACD calculation
            request = f"Get MACD data for {symbol} on {date}"
            response = self.tech_agent.generate_reply(request)
            
            # Parse TechAgent JSON response
            tech_data = json.loads(response)
            macd_today = tech_data.get('macd_today')
            macd_yest = tech_data.get('macd_yest')
            
            if macd_today is None or macd_yest is None:
                return None
                
            # Convert MACD histogram to signal strength
            signal_strength = self._macd_to_signal_strength(macd_today, macd_yest)
            confidence = min(abs(macd_today) * 10, 1.0)  # Scale confidence
            
            return IndicatorSignal(
                indicator_name="MACD",
                signal_strength=signal_strength,
                confidence=confidence,
                raw_value=macd_today,
                timestamp=date
            )
            
        except Exception as e:
            logger.error(f"Error getting MACD signal: {e}")
            return None
    
    def get_sentiment_signal(
        self, version: str, symbol: str, date: str
    ) -> Optional[IndicatorSignal]:
        """Get sentiment signal from V0-V4 agents"""
        if version not in self.sentiment_agents:
            logger.warning(f"No sentiment agent registered for V{version}")
            return None
            
        try:
            # This would integrate with existing sentiment agent patterns
            # Implementation will be completed as sentiment agents are integrated
            # sentiment_agent = self.sentiment_agents[version]
            # request = f"Analyze sentiment for {symbol} on {date}"
            
            # Placeholder for now - will be implemented with Issue #277+ 
            return IndicatorSignal(
                indicator_name=f"Sentiment_V{version}",
                signal_strength=0,  # Neutral for now
                confidence=0.5,
                raw_value=0.5,
                timestamp=date
            )
            
        except Exception as e:
            logger.error(f"Error getting V{version} sentiment signal: {e}")
            return None
    
    # ==================== Utility Methods ====================
    
    def _macd_to_signal_strength(self, macd_today: float, macd_yest: float) -> int:
        """Convert MACD histogram values to signal strength"""
        # MACD crossover logic from existing V0-V4 system
        if macd_today > 0 > macd_yest:  # Bullish crossover
            return SignalStrength.BULLISH.value
        elif macd_today < 0 < macd_yest:  # Bearish crossover  
            return SignalStrength.BEARISH.value
        elif macd_today > 0:  # Above zero
            return SignalStrength.WEAK_BULLISH.value
        elif macd_today < 0:  # Below zero
            return SignalStrength.WEAK_BEARISH.value
        else:
            return SignalStrength.NEUTRAL.value
    
    def record_decision(self, decision: VotingDecision):
        """Record voting decision for performance tracking"""
        self.decision_history.append({
            'timestamp': pd.Timestamp.now().isoformat(),
            'decision': decision.action,
            'confidence': decision.confidence,
            'weighted_score': decision.weighted_score,
            'regime': decision.market_regime.value if decision.market_regime else None,
            'breakdown': {k: v.signal_strength for k, v in decision.vote_breakdown.items()}
        })
        
        # Keep last 1000 decisions for analysis
        if len(self.decision_history) > 1000:
            self.decision_history = self.decision_history[-1000:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get voting performance metrics"""
        if not self.decision_history:
            return {"message": "No decisions recorded yet"}
            
        decisions = pd.DataFrame(self.decision_history)
        
        return {
            "total_decisions": len(decisions),
            "action_distribution": decisions['decision'].value_counts().to_dict(),
            "average_confidence": decisions['confidence'].mean(),
            "regime_distribution": (
                decisions['regime'].value_counts().to_dict() 
                if 'regime' in decisions else {}
            ),
            "recent_decisions": decisions.tail(10).to_dict('records')
        }
    
    # ==================== AutoGen Interface ====================
    
    def generate_reply(self, messages, context=None) -> str:
        """
        AutoGen interface for voting decisions.
        
        Expected message format: {
            "action": "vote",
            "symbol": "AAPL", 
            "date": "2024-01-15",
            "market_data": {...}
        }
        """
        try:
            # Parse message
            if isinstance(messages, str):
                request_data = {"action": "vote", "symbol": "AAPL", "date": "2024-01-15"}
            elif isinstance(messages, dict):
                request_data = messages
            elif isinstance(messages, list) and messages:
                last_msg = messages[-1]
                if isinstance(last_msg, dict):
                    request_data = last_msg.get("content", {})
                else:
                    request_data = {"action": "vote", "symbol": "AAPL", "date": "2024-01-15"}
            else:
                request_data = {"action": "vote", "symbol": "AAPL", "date": "2024-01-15"}
                
            symbol = request_data.get("symbol", "AAPL")
            date = request_data.get("date", "2024-01-15") 
            market_data = request_data.get("market_data", {})
            
            # Get all indicator signals
            signals = self.calculate_indicator_signals(symbol, date, market_data)
            
            # Determine market regime
            regime = self.determine_market_regime(market_data)
            
            # Calculate weighted vote
            decision = self.calculate_weighted_vote(signals, regime)
            
            # Record decision
            self.record_decision(decision)
            
            # Return decision as JSON
            return json.dumps({
                "action": decision.action,
                "confidence": decision.confidence,
                "weighted_score": decision.weighted_score,
                "regime": decision.market_regime.value if decision.market_regime else None,
                "reasoning": decision.reasoning,
                "signal_breakdown": {
                    name: {
                        "strength": signal.signal_strength,
                        "confidence": signal.confidence,
                        "raw_value": signal.raw_value
                    }
                    for name, signal in decision.vote_breakdown.items()
                }
            })
            
        except Exception as e:
            logger.error(f"Error in voting decision: {e}")
            return json.dumps({
                "action": "HOLD",
                "confidence": 0.0,
                "error": str(e)
            })