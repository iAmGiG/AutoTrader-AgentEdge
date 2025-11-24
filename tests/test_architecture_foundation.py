"""
Basic tests for plugin architecture foundation.

Tests validate that core components work correctly before building more.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from unittest.mock import AsyncMock

import pytest
from core.models import (
    AnalysisResult,
    AssetType,
    OrderType,
    RiskAssessment,
    Signal,
    TimeInForce,
    TradeRequest,
    TradeSuggestion,
)
from core.trading_orchestrator import TradingOrchestrator
from strategies.voter_strategy import VoterStrategy


class TestCoreModels:
    """Test that core models can be created and are valid."""

    def test_trade_request_creation(self):
        """Test creating a TradeRequest."""
        request = TradeRequest(
            ticker="SPY", action="review", quantity=10, price=600.0, asset_type=AssetType.STOCK
        )

        assert request.ticker == "SPY"
        assert request.action == "review"
        assert request.quantity == 10
        assert request.price == 600.0
        assert request.asset_type == AssetType.STOCK

    def test_analysis_result_creation(self):
        """Test creating an AnalysisResult."""
        analysis = AnalysisResult(
            signal=Signal.BUY,
            confidence=0.75,
            entry_price=600.0,
            stop_loss=588.0,
            take_profit=620.0,
            reasoning=["Test reason 1", "Test reason 2"],
            analyzer_name="TestAnalyzer",
        )

        assert analysis.signal == Signal.BUY
        assert analysis.confidence == 0.75
        assert len(analysis.reasoning) == 2

    def test_risk_assessment_creation(self):
        """Test creating a RiskAssessment."""
        risk = RiskAssessment(
            approved=True,
            recommended_quantity=10,
            portfolio_pct=5.0,
            max_loss_usd=120.0,
            risk_reward_ratio=1.6,
            warnings=["Test warning"],
        )

        assert risk.approved is True
        assert risk.recommended_quantity == 10
        assert len(risk.warnings) == 1

    def test_trade_suggestion_creation(self):
        """Test creating a TradeSuggestion."""
        suggestion = TradeSuggestion(
            signal=Signal.BUY,
            confidence=0.75,
            entry_price=600.0,
            stop_loss=588.0,
            take_profit=620.0,
            reasoning=["Test"],
            recommended_quantity=10,
            portfolio_pct=5.0,
            max_loss_usd=120.0,
            risk_reward_ratio=1.6,
            warnings=[],
            ticker="SPY",
            order_type=OrderType.LIMIT,
            time_in_force=TimeInForce.GTC,
        )

        assert suggestion.ticker == "SPY"
        assert suggestion.time_in_force == TimeInForce.GTC


class TestVoterStrategyStub:
    """Test VoterStrategy stub returns valid analysis."""

    @pytest.mark.asyncio
    async def test_voter_strategy_analyze(self):
        """Test VoterStrategy.analyze() returns valid AnalysisResult."""
        strategy = VoterStrategy()

        request = TradeRequest(ticker="SPY", action="review", price=600.0)

        result = await strategy.analyze(request)

        # Check result is valid
        assert isinstance(result, AnalysisResult)
        assert result.signal in [Signal.BUY, Signal.SELL, Signal.HOLD]
        assert 0.0 <= result.confidence <= 1.0
        assert result.entry_price > 0
        assert result.stop_loss > 0
        assert result.take_profit > 0
        assert len(result.reasoning) > 0
        assert result.indicators.get("is_stub") is True  # Verify it's stub

    @pytest.mark.asyncio
    async def test_voter_strategy_uses_request_price(self):
        """Test that VoterStrategy uses price from request."""
        strategy = VoterStrategy()

        request = TradeRequest(ticker="AAPL", action="review", price=150.0)

        result = await strategy.analyze(request)

        assert result.entry_price == 150.0
        assert result.stop_loss == 150.0 * 0.98  # -2%
        assert result.take_profit == 150.0 * 1.035  # +3.5%

    def test_voter_strategy_name(self):
        """Test VoterStrategy properties."""
        strategy = VoterStrategy()

        assert strategy.name == "VoterStrategy"
        assert AssetType.STOCK in strategy.supported_asset_types


class TestTradingOrchestratorWithMocks:
    """Test TradingOrchestrator workflow with mocked components."""

    @pytest.mark.asyncio
    async def test_orchestrator_process_request_flow(self):
        """Test complete process_request workflow with mocks."""
        # Create mocks
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = TradeRequest(ticker="SPY", action="review", price=600.0)
        mock_parser.validate.return_value = True

        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = AnalysisResult(
            signal=Signal.BUY,
            confidence=0.75,
            entry_price=600.0,
            stop_loss=588.0,
            take_profit=620.0,
            reasoning=["Mock analysis"],
            analyzer_name="MockAnalyzer",
        )
        mock_analyzer.name = "MockAnalyzer"

        mock_risk = AsyncMock()
        mock_risk.assess.return_value = RiskAssessment(
            approved=True,
            recommended_quantity=10,
            portfolio_pct=5.0,
            max_loss_usd=120.0,
            risk_reward_ratio=1.6,
            warnings=[],
        )

        mock_executor = AsyncMock()

        # Create orchestrator
        orchestrator = TradingOrchestrator(
            input_parser=mock_parser,
            strategy_analyzer=mock_analyzer,
            risk_manager=mock_risk,
            execution_manager=mock_executor,
            session_store=None,  # Optional
        )

        # Process request
        decision = await orchestrator.process_request("is SPY at 600 good?", "test_user")

        # Verify workflow
        assert mock_parser.parse.called
        assert mock_parser.validate.called
        assert mock_analyzer.analyze.called
        assert mock_risk.assess.called

        # Verify decision
        assert decision.suggestion.signal == Signal.BUY
        assert decision.suggestion.ticker == "SPY"
        assert decision.suggestion.recommended_quantity == 10
        assert decision.suggestion.time_in_force == TimeInForce.GTC  # Always GTC
        assert decision.approved is False  # Awaiting user confirmation

    @pytest.mark.asyncio
    async def test_orchestrator_suggestion_creation(self):
        """Test that orchestrator creates proper suggestions."""
        # Minimal mocks
        mock_parser = AsyncMock()
        mock_parser.parse.return_value = TradeRequest(ticker="AAPL", action="buy", quantity=50)
        mock_parser.validate.return_value = True

        mock_analyzer = AsyncMock()
        mock_analyzer.analyze.return_value = AnalysisResult(
            signal=Signal.BUY,
            confidence=0.8,
            entry_price=150.0,
            stop_loss=147.0,
            take_profit=156.0,
            reasoning=["Strong buy signal"],
            analyzer_name="Test",
        )
        mock_analyzer.name = "Test"

        mock_risk = AsyncMock()
        mock_risk.assess.return_value = RiskAssessment(
            approved=True,
            recommended_quantity=40,  # Risk manager suggests different qty
            portfolio_pct=8.0,
            max_loss_usd=150.0,
            risk_reward_ratio=2.0,
            warnings=["High allocation"],
        )

        mock_executor = AsyncMock()

        orchestrator = TradingOrchestrator(
            input_parser=mock_parser,
            strategy_analyzer=mock_analyzer,
            risk_manager=mock_risk,
            execution_manager=mock_executor,
        )

        decision = await orchestrator.process_request("buy 50 AAPL", "test_user")

        # Verify suggestion uses user's quantity (not risk manager's recommendation)
        assert decision.suggestion.recommended_quantity == 50
        assert decision.suggestion.warnings == ["High allocation"]


def run_tests():
    """Run all tests and report results."""
    print("=" * 70)
    print("RUNNING ARCHITECTURE FOUNDATION TESTS")
    print("=" * 70)

    # Run pytest
    exit_code = pytest.main(
        [
            __file__,
            "-v",  # Verbose
            "--tb=short",  # Short traceback
            "-s",  # Show print statements
        ]
    )

    return exit_code


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
