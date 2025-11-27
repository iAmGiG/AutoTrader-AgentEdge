"""
RiskManager interface.

Defines the contract for risk assessment and position sizing.
Implementations can range from simple (portfolio %) to sophisticated (Portfolio Manager).
"""

from abc import ABC, abstractmethod

from ..models import AnalysisResult, RiskAssessment, TradeRequest


class RiskManager(ABC):
    """
    Abstract interface for risk management and position sizing.

    Implementations:
    - SimpleRiskManager: Basic portfolio % and buying power check (MVP)
    - PortfolioManager: Full risk management with sector limits, correlation, etc. (#333)
    """

    @abstractmethod
    async def assess(
        self, request: TradeRequest, analysis: AnalysisResult, user_id: str = "default"
    ) -> RiskAssessment:
        """
        Assess risk and recommend position size.

        Args:
            request: Original trade request
            analysis: Strategy analysis result
            user_id: User ID for portfolio lookup

        Returns:
            RiskAssessment with approved flag, recommended quantity, warnings

        The risk manager should:
        1. Check buying power
        2. Calculate position size based on portfolio %
        3. Check for existing positions
        4. Evaluate risk (max loss based on stop-loss)
        5. Generate warnings (but not block unless critical)
        """
        pass

    @abstractmethod
    async def get_portfolio_value(self, user_id: str = "default") -> float:
        """
        Get total portfolio value for user.

        Args:
            user_id: User ID

        Returns:
            Total portfolio value in USD
        """
        pass

    @abstractmethod
    async def get_buying_power(self, user_id: str = "default") -> float:
        """
        Get available buying power for user.

        Args:
            user_id: User ID

        Returns:
            Available cash in USD
        """
        pass
