"""
StrategyAnalyzer interface.

Defines the contract for analyzing trade requests and generating signals.
Implementations can use different strategies (MACD+RSI, options, multi-agent).
"""

from abc import ABC, abstractmethod
from ..models import TradeRequest, AnalysisResult


class StrategyAnalyzer(ABC):
    """
    Abstract interface for trade strategy analysis.

    Implementations:
    - VoterStrategy: MACD+RSI voting (current production system)
    - OptionsStrategy: Options-specific analysis (Greeks, IV, OI)
    - MultiAgentStrategy: Multiple agents debate and reach consensus
    """

    @abstractmethod
    async def analyze(self, request: TradeRequest) -> AnalysisResult:
        """
        Analyze trade request and generate signal.

        Args:
            request: Parsed trade request

        Returns:
            AnalysisResult with signal, confidence, entry/stop/target, reasoning

        Raises:
            ValueError: If request cannot be analyzed (e.g., invalid ticker)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the strategy (e.g., 'VoterStrategy', 'OptionsStrategy')"""
        pass

    @property
    @abstractmethod
    def supported_asset_types(self) -> list:
        """List of AssetType enums this strategy supports"""
        pass
