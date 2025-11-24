#!/usr/bin/env python3
"""
Basic tests for plugin architecture (no pytest required).

Run: python3 tests/test_basic.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import asyncio
from unittest.mock import AsyncMock


def test_core_models():
    """Test that core models can be created."""
    print("\n=== Test 1: Core Models ===")

    from core.models import (
        AnalysisResult,
        AssetType,
        RiskAssessment,
        Signal,
        TradeRequest,
    )

    # Test TradeRequest
    request = TradeRequest(
        ticker="SPY", action="review", quantity=10, price=600.0, asset_type=AssetType.STOCK
    )
    assert request.ticker == "SPY", "TradeRequest ticker failed"
    assert request.quantity == 10, "TradeRequest quantity failed"
    print("✅ TradeRequest creation: PASS")

    # Test AnalysisResult
    analysis = AnalysisResult(
        signal=Signal.BUY,
        confidence=0.75,
        entry_price=600.0,
        stop_loss=588.0,
        take_profit=620.0,
        reasoning=["Test reason"],
        analyzer_name="TestAnalyzer",
    )
    assert analysis.signal == Signal.BUY, "AnalysisResult signal failed"
    assert analysis.confidence == 0.75, "AnalysisResult confidence failed"
    print("✅ AnalysisResult creation: PASS")

    # Test RiskAssessment
    risk = RiskAssessment(
        approved=True,
        recommended_quantity=10,
        portfolio_pct=5.0,
        max_loss_usd=120.0,
        risk_reward_ratio=1.6,
    )
    assert risk.approved is True, "RiskAssessment approved failed"
    assert risk.recommended_quantity == 10, "RiskAssessment quantity failed"
    print("✅ RiskAssessment creation: PASS")

    return True


async def test_voter_strategy_stub():
    """Test VoterStrategy stub returns valid analysis."""
    print("\n=== Test 2: VoterStrategy Stub ===")

    from core.models import AnalysisResult, Signal, TradeRequest
    from strategies.voter_strategy import VoterStrategy

    strategy = VoterStrategy()

    # Test with price specified
    request = TradeRequest(ticker="SPY", action="review", price=600.0)

    result = await strategy.analyze(request)

    # Validate result
    assert isinstance(result, AnalysisResult), "Result not AnalysisResult"
    assert result.signal in [Signal.BUY, Signal.SELL, Signal.HOLD], "Invalid signal"
    assert 0.0 <= result.confidence <= 1.0, "Invalid confidence"
    assert result.entry_price == 600.0, f"Entry price wrong: {result.entry_price}"
    assert result.stop_loss > 0, "Stop loss invalid"
    assert result.take_profit > 0, "Take profit invalid"
    assert len(result.reasoning) > 0, "No reasoning provided"
    assert result.indicators.get("is_stub") is True, "Not flagged as stub"

    print(f"✅ VoterStrategy analyze: {result.signal.value} signal at {result.entry_price}")
    print(f"   Confidence: {result.confidence:.1%}")
    print(f"   Stop: {result.stop_loss:.2f}, Target: {result.take_profit:.2f}")
    print("✅ VoterStrategy stub: PASS")

    return True


async def test_orchestrator_workflow():
    """Test TradingOrchestrator with mocked components."""
    print("\n=== Test 3: TradingOrchestrator Workflow ===")

    from core.models import AnalysisResult, RiskAssessment, Signal, TradeRequest
    from core.trading_orchestrator import TradingOrchestrator

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
        session_store=None,
    )

    # Process request
    decision = await orchestrator.process_request("is SPY at 600 good?", "test_user")

    # Verify workflow was called
    assert mock_parser.parse.called, "Parser not called"
    assert mock_parser.validate.called, "Validator not called"
    assert mock_analyzer.analyze.called, "Analyzer not called"
    assert mock_risk.assess.called, "Risk manager not called"

    # Verify decision
    assert decision.suggestion.signal == Signal.BUY, "Wrong signal in decision"
    assert decision.suggestion.ticker == "SPY", "Wrong ticker in decision"
    assert decision.suggestion.recommended_quantity == 10, "Wrong quantity"
    assert decision.approved is False, "Should not be auto-approved"

    print("✅ Workflow executed: parse → analyze → risk → suggest")
    print(
        f"   Suggestion: {decision.suggestion.signal.value} {decision.suggestion.recommended_quantity} {decision.suggestion.ticker}"
    )
    print(
        f"   Entry: {decision.suggestion.entry_price}, Stop: {decision.suggestion.stop_loss}, Target: {decision.suggestion.take_profit}"
    )
    print("✅ TradingOrchestrator workflow: PASS")

    return True


async def test_orchestrator_suggestion_merging():
    """Test that orchestrator properly merges analysis + risk assessment."""
    print("\n=== Test 4: Suggestion Merging ===")

    from core.models import (
        AnalysisResult,
        RiskAssessment,
        Signal,
        TimeInForce,
        TradeRequest,
    )
    from core.trading_orchestrator import TradingOrchestrator

    # Create mocks with specific values to test merging
    mock_parser = AsyncMock()
    mock_parser.parse.return_value = TradeRequest(ticker="AAPL", action="buy", quantity=50)
    mock_parser.validate.return_value = True

    mock_analyzer = AsyncMock()
    mock_analyzer.analyze.return_value = AnalysisResult(
        signal=Signal.BUY,
        confidence=0.85,
        entry_price=150.0,
        stop_loss=147.0,
        take_profit=156.0,
        reasoning=["Strong momentum", "RSI oversold"],
        analyzer_name="TestAnalyzer",
    )
    mock_analyzer.name = "TestAnalyzer"

    mock_risk = AsyncMock()
    mock_risk.assess.return_value = RiskAssessment(
        approved=True,
        recommended_quantity=40,  # Different from request
        portfolio_pct=8.0,
        max_loss_usd=150.0,
        risk_reward_ratio=2.0,
        warnings=["High allocation warning"],
    )

    mock_executor = AsyncMock()

    orchestrator = TradingOrchestrator(
        input_parser=mock_parser,
        strategy_analyzer=mock_analyzer,
        risk_manager=mock_risk,
        execution_manager=mock_executor,
    )

    decision = await orchestrator.process_request("buy 50 AAPL", "test_user")

    # Verify suggestion merges both sources correctly
    suggestion = decision.suggestion

    # From analysis
    assert suggestion.signal == Signal.BUY, "Signal not from analysis"
    assert suggestion.confidence == 0.85, "Confidence not from analysis"
    assert suggestion.entry_price == 150.0, "Entry not from analysis"
    assert suggestion.reasoning == [
        "Strong momentum",
        "RSI oversold",
    ], "Reasoning not from analysis"

    # From risk (but user qty takes precedence)
    assert suggestion.recommended_quantity == 50, "Should use user quantity"
    assert suggestion.portfolio_pct == 8.0, "Portfolio % not from risk"
    assert suggestion.warnings == ["High allocation warning"], "Warnings not from risk"

    # Orchestrator enforces GTC
    assert suggestion.time_in_force == TimeInForce.GTC, "Should always be GTC"

    print("✅ Suggestion merged correctly:")
    print(f"   Analysis: {suggestion.signal.value} @ {suggestion.entry_price}")
    print(
        f"   Risk: {suggestion.recommended_quantity} shares ({suggestion.portfolio_pct}% portfolio)"
    )
    print(f"   Order: {suggestion.time_in_force.value}")
    print("✅ Suggestion merging: PASS")

    return True


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 70)
    print("ARCHITECTURE FOUNDATION TESTS")
    print("=" * 70)

    results = []

    # Test 1: Models
    try:
        result = test_core_models()
        results.append(("Core Models", result))
    except Exception as e:
        print(f"❌ Core Models: FAILED - {e}")
        results.append(("Core Models", False))

    # Test 2: VoterStrategy
    try:
        result = asyncio.run(test_voter_strategy_stub())
        results.append(("VoterStrategy Stub", result))
    except Exception as e:
        print(f"❌ VoterStrategy Stub: FAILED - {e}")
        results.append(("VoterStrategy Stub", False))
        import traceback

        traceback.print_exc()

    # Test 3: Orchestrator workflow
    try:
        result = asyncio.run(test_orchestrator_workflow())
        results.append(("Orchestrator Workflow", result))
    except Exception as e:
        print(f"❌ Orchestrator Workflow: FAILED - {e}")
        results.append(("Orchestrator Workflow", False))
        import traceback

        traceback.print_exc()

    # Test 4: Suggestion merging
    try:
        result = asyncio.run(test_orchestrator_suggestion_merging())
        results.append(("Suggestion Merging", result))
    except Exception as e:
        print(f"❌ Suggestion Merging: FAILED - {e}")
        results.append(("Suggestion Merging", False))
        import traceback

        traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Architecture foundation is solid!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review errors above")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
