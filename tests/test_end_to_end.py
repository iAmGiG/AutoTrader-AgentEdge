"""
End-to-end integration test for trade-assist workflow.

Tests the complete flow from CLI → Orchestrator → Components → Result.
"""

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from cli import CLISession
from core.factory import OrchestratorFactory
from core.trading_orchestrator import TradingOrchestrator
from core.models import *


async def test_orchestrator_creation():
    """Test that OrchestratorFactory creates a valid orchestrator."""
    print("\n[Test 1] OrchestratorFactory creates orchestrator...")

    factory = OrchestratorFactory()
    orchestrator = factory.create(order_manager=None)

    # Verify all components wired
    assert orchestrator.parser is not None, "Parser should be wired"
    assert orchestrator.analyzer is not None, "Analyzer should be wired"
    assert orchestrator.risk is not None, "Risk manager should be wired"
    assert orchestrator.executor is not None, "Executor should be wired"

    print("   ✅ Orchestrator created with all components")


async def test_complete_workflow():
    """Test complete workflow: parse → analyze → risk → suggest."""
    print("\n[Test 2] Complete workflow (parse → analyze → risk → suggest) with mocks...")

    # Create mocked components
    mock_parser = AsyncMock()
    mock_analyzer = AsyncMock()
    mock_risk = AsyncMock()
    mock_executor = AsyncMock()

    # Configure mock parser
    mock_parser.parse.return_value = TradeRequest(
        ticker="SPY",
        action="review",
        price=600.0,
        raw_input="is SPY at 600 a good entry?"
    )
    mock_parser.validate.return_value = True

    # Configure mock analyzer
    mock_analyzer.analyze.return_value = AnalysisResult(
        signal=Signal.BUY,
        confidence=0.75,
        entry_price=600.0,
        stop_loss=588.0,
        take_profit=621.0,
        reasoning=["MACD: BUY (bullish crossover)", "RSI: NEUTRAL (value: 52)"],
        indicators={"macd_histogram": 1.5, "rsi": 52},
        analyzer_name="VoterStrategy"
    )
    mock_analyzer.supported_asset_types = [AssetType.STOCK]
    mock_analyzer.name = "VoterStrategy (Mock)"

    # Configure mock risk manager
    mock_risk.assess.return_value = RiskAssessment(
        approved=True,
        recommended_quantity=8,
        portfolio_pct=4.8,
        max_loss_usd=96.0,
        risk_reward_ratio=2.2,
        warnings=[]
    )

    # Create orchestrator with mocks
    orchestrator = TradingOrchestrator(
        input_parser=mock_parser,
        strategy_analyzer=mock_analyzer,
        risk_manager=mock_risk,
        execution_manager=mock_executor
    )

    # Process a trade request
    user_input = "is SPY at 600 a good entry?"
    decision = await orchestrator.process_request(user_input, user_id="test_user")

    # Verify decision structure
    assert decision is not None, "Decision should be returned"
    assert decision.suggestion is not None, "Suggestion should be present"
    assert decision.suggestion.ticker == "SPY", f"Expected SPY, got {decision.suggestion.ticker}"
    assert decision.suggestion.entry_price == 600.0, "Entry price should be 600"
    assert decision.suggestion.stop_loss == 588.0, "Stop loss should be 588"
    assert decision.suggestion.take_profit == 621.0, "Take profit should be 621"
    assert decision.suggestion.recommended_quantity == 8, "Quantity should be 8"
    assert len(decision.suggestion.reasoning) > 0, "Reasoning should be provided"

    print(f"   ✅ Workflow complete")
    print(f"      Ticker: {decision.suggestion.ticker}")
    print(f"      Signal: {decision.suggestion.signal.value}")
    print(f"      Entry: ${decision.suggestion.entry_price:.2f}")
    print(f"      Stop: ${decision.suggestion.stop_loss:.2f}")
    print(f"      Target: ${decision.suggestion.take_profit:.2f}")
    print(f"      Qty: {decision.suggestion.recommended_quantity}")


async def test_execution_stub():
    """Test execution in stub mode."""
    print("\n[Test 3] Execution in stub mode with mocks...")

    # Create mocked components
    mock_parser = AsyncMock()
    mock_analyzer = AsyncMock()
    mock_risk = AsyncMock()
    mock_executor = AsyncMock()

    # Configure mocks for AAPL buy
    mock_parser.parse.return_value = TradeRequest(
        ticker="AAPL",
        action="buy",
        quantity=10,
        price=200.0,
        raw_input="buy 10 AAPL at 200"
    )
    mock_parser.validate.return_value = True

    mock_analyzer.analyze.return_value = AnalysisResult(
        signal=Signal.BUY,
        confidence=0.80,
        entry_price=200.0,
        stop_loss=196.0,
        take_profit=207.0,
        reasoning=["User requested buy"],
        indicators={},
        analyzer_name="VoterStrategy"
    )
    mock_analyzer.supported_asset_types = [AssetType.STOCK]
    mock_analyzer.name = "VoterStrategy (Mock)"

    mock_risk.assess.return_value = RiskAssessment(
        approved=True,
        recommended_quantity=10,
        portfolio_pct=2.0,
        max_loss_usd=40.0,
        risk_reward_ratio=1.75,
        warnings=[]
    )

    mock_executor.execute_trade.return_value = OrderResult(
        success=True,
        entry_order_id="STUB_ENTRY_123",
        stop_order_id="STUB_STOP_456",
        target_order_id="STUB_TARGET_789",
        ticker="AAPL",
        quantity=10,
        message="Order placed successfully (STUB MODE)"
    )

    # Create orchestrator with mocks
    orchestrator = TradingOrchestrator(
        input_parser=mock_parser,
        strategy_analyzer=mock_analyzer,
        risk_manager=mock_risk,
        execution_manager=mock_executor
    )

    # Process and approve
    user_input = "buy 10 AAPL at 200"
    decision = await orchestrator.process_request(user_input, user_id="test_user")
    decision.approved = True

    # Execute
    result = await orchestrator.execute_decision(decision)

    # Verify result
    assert result is not None, "Result should be returned"
    assert result.success, "Stub execution should succeed"
    assert result.entry_order_id.startswith("STUB_"), "Should have stub order ID"
    assert result.ticker == "AAPL", f"Expected AAPL, got {result.ticker}"

    print(f"   ✅ Execution successful (stub mode)")
    print(f"      Order ID: {result.entry_order_id}")
    print(f"      Message: {result.message}")


async def test_cli_session_creation():
    """Test that CLISession can be created."""
    print("\n[Test 4] CLISession creation...")

    # Create mock orchestrator
    mock_orchestrator = MagicMock()

    session = CLISession(mock_orchestrator)

    assert session.orchestrator is not None, "Orchestrator should be set"
    assert session.autonomy_mode == "confirm", "Default mode should be confirm"
    assert session.user_id == "cli_user", "User ID should be set"

    print("   ✅ CLISession created successfully")


async def run_all_tests():
    """Run all end-to-end tests."""
    print("=" * 70)
    print("END-TO-END INTEGRATION TESTS")
    print("=" * 70)

    try:
        await test_orchestrator_creation()
        await test_complete_workflow()
        await test_execution_stub()
        await test_cli_session_creation()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED (4/4)")
        print("=" * 70)
        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Set environment variable for OpenAI (stub will be used anyway)
    os.environ.setdefault('OPENAI_API_KEY', 'test-key')

    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
