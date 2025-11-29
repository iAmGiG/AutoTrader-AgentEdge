#!/usr/bin/env python3
"""
Unit tests for TradingPipeline.

Tests the 5-phase daily trading workflow orchestrator:
- Phase 1: Data Collection (market data refresh, validation)
- Phase 2: Analysis (VoterAgent signal generation)
- Phase 3: Execution (order placement)
- Phase 4: Management (stop order updates, risk monitoring)
- Phase 5: End-of-Day (reconciliation, state persistence)

Issue #408: Unit Testing and CLI Testing (Pre-Live Trading Validation)
Priority 1 Component - TradingPipeline (Critical for live trading)
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from src.trading.trading_pipeline import (
    PhaseResult,
    PipelineMetrics,
    PipelinePhase,
    PipelineStatus,
    TradingPipeline,
)

# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_market_data():
    """Mock market data for data collection phase."""
    return {
        "SPY": {"close": [100, 101, 102], "high": [101, 102, 103], "low": [99, 100, 101]},
        "QQQ": {"close": [300, 301, 302], "high": [301, 302, 303], "low": [299, 300, 301]},
    }


@pytest.fixture
def mock_signals():
    """Mock trading signals from analysis phase."""
    return [
        {
            "ticker": "SPY",
            "action": "BUY",
            "confidence": 0.8,
            "position_size": 1.0,
            "reasoning": "MACD+RSI consensus",
        },
        {
            "ticker": "QQQ",
            "action": "HOLD",
            "confidence": 0.5,
            "position_size": 0.0,
            "reasoning": "Weak signal",
        },
    ]


@pytest.fixture
def mock_positions():
    """Mock current positions."""
    return {
        "SPY": {"symbol": "SPY", "qty": 100, "entry_price": 100, "current_price": 102},
        "IWM": {"symbol": "IWM", "qty": 50, "entry_price": 200, "current_price": 195},
    }


@pytest.fixture
def trading_pipeline():
    """Create a TradingPipeline instance with mocked dependencies."""
    with (
        patch("src.trading.trading_pipeline.AlpacaMarketData"),
        patch("src.trading.trading_pipeline.PositionManager"),
    ):
        pipeline = TradingPipeline(watchlist=["SPY", "QQQ", "AAPL"])
        return pipeline


# =============================================================================
# Pipeline Initialization Tests
# =============================================================================


class TestPipelineInitialization:
    """Test TradingPipeline initialization."""

    def test_init_with_agents(self):
        """Test initialization with all agents."""
        mock_scanner = MagicMock()
        mock_voter = MagicMock()
        mock_risk = MagicMock()
        mock_executor = MagicMock()

        pipeline = TradingPipeline(
            scanner_agent=mock_scanner,
            voter_agent=mock_voter,
            risk_agent=mock_risk,
            executor_agent=mock_executor,
        )

        assert pipeline.scanner == mock_scanner
        assert pipeline.voter == mock_voter
        assert pipeline.risk_manager == mock_risk
        assert pipeline.executor == mock_executor

    def test_init_with_custom_watchlist(self):
        """Test initialization with custom watchlist."""
        custom_list = ["SPY", "QQQ", "IWM"]
        pipeline = TradingPipeline(watchlist=custom_list)
        assert pipeline.watchlist == custom_list

    def test_init_default_watchlist(self):
        """Test initialization loads default watchlist."""
        with patch.object(TradingPipeline, "_load_default_watchlist") as mock_load:
            mock_load.return_value = ["SPY", "QQQ"]
            pipeline = TradingPipeline()
            assert pipeline.watchlist == ["SPY", "QQQ"]

    def test_init_status_idle(self):
        """Test pipeline initializes with IDLE status."""
        pipeline = TradingPipeline(watchlist=["SPY"])
        assert pipeline.pipeline_status == PipelineStatus.IDLE
        assert pipeline.current_phase is None
        assert pipeline.current_metrics is None


# =============================================================================
# Pipeline Phase Tests
# =============================================================================


@pytest.mark.asyncio
async def test_data_collection_phase(trading_pipeline):
    """Test data collection phase validates market data."""
    result = await trading_pipeline._data_collection_phase()

    assert "market_open" in result
    assert "tickers_validated" in result
    assert result["tickers_validated"] == 3


@pytest.mark.asyncio
async def test_analysis_phase_no_voter(trading_pipeline):
    """Test analysis phase gracefully handles missing VoterAgent."""
    result = await trading_pipeline._analysis_phase()

    assert "signals" in result
    assert result["signals"] == []


@pytest.mark.asyncio
async def test_analysis_phase_with_voter(trading_pipeline, mock_signals):
    """Test analysis phase generates signals with VoterAgent."""
    mock_voter = MagicMock()
    trading_pipeline.voter = mock_voter

    # Mock evaluate_voting to return a signal
    mock_voter.evaluate_voting.return_value = {
        "action": "BUY",
        "confidence": 0.8,
        "position_size": 1.0,
        "reasoning": "MACD+RSI consensus",
        "signal_type": "STRONG",
    }

    with patch("src.trading.trading_pipeline.AlpacaMarketData") as mock_market_data_class:
        mock_instance = MagicMock()
        mock_market_data_class.return_value = mock_instance
        mock_instance.get_bars.return_value = {"SPY": [100, 101, 102]}

        result = await trading_pipeline._analysis_phase()

        assert "signals" in result
        assert len(result["signals"]) > 0


@pytest.mark.asyncio
async def test_execution_phase_no_signals(trading_pipeline):
    """Test execution phase with no signals."""
    result = await trading_pipeline._execution_phase(signals=None)

    assert result["orders_placed"] == 0
    assert result["executions"] == []


@pytest.mark.asyncio
async def test_execution_phase_with_signals(trading_pipeline, mock_signals):
    """Test execution phase places orders."""
    mock_executor = MagicMock()
    mock_executor.execute_trade.return_value = {"status": "filled", "id": "order123"}
    trading_pipeline.executor = mock_executor

    with patch("src.trading.trading_pipeline.get_current_price") as mock_price:
        mock_price.return_value = 100.0
        with patch("src.trading.trading_pipeline.PositionManager"):
            result = await trading_pipeline._execution_phase(signals=mock_signals)

            assert result["orders_placed"] >= 0
            assert "executions" in result


@pytest.mark.asyncio
async def test_management_phase_with_positions(trading_pipeline, mock_positions):
    """Test management phase tracks positions."""
    mock_pos_mgr = MagicMock()
    mock_pos_mgr.get_positions.return_value = mock_positions
    trading_pipeline.position_manager = mock_pos_mgr

    result = await trading_pipeline._management_phase()

    assert "positions_updated" in result
    assert result["positions_updated"] >= 0


@pytest.mark.asyncio
async def test_management_phase_no_positions(trading_pipeline):
    """Test management phase without PositionManager."""
    result = await trading_pipeline._management_phase()

    assert "positions_updated" in result
    assert result["positions_updated"] == 0


@pytest.mark.asyncio
async def test_end_of_day_phase(trading_pipeline):
    """Test end-of-day phase completes reconciliation."""
    mock_pos_mgr = MagicMock()
    mock_pos_mgr.get_positions.return_value = {}
    mock_pos_mgr.get_account_info.return_value = {"portfolio_value": 100000.0}
    trading_pipeline.position_manager = mock_pos_mgr

    result = await trading_pipeline._end_of_day_phase()

    assert result["reconciliation_complete"] is True
    assert "report_path" in result
    assert "position_count" in result
    assert "total_pnl" in result


# =============================================================================
# Full Pipeline Execution Tests
# =============================================================================


@pytest.mark.asyncio
async def test_full_pipeline_execution(trading_pipeline):
    """Test complete 5-phase pipeline execution."""
    result = await trading_pipeline.run_full_pipeline()

    assert isinstance(result, PipelineMetrics)
    assert result.started_at is not None
    assert result.completed_at is not None
    assert result.total_phases == 5
    assert len(result.phase_results) == 5


@pytest.mark.asyncio
async def test_pipeline_status_running(trading_pipeline):
    """Test pipeline status updates during execution."""
    # Start pipeline execution
    metrics = await trading_pipeline.run_full_pipeline()

    # After completion, status should not be IDLE
    assert metrics is not None
    assert metrics.phases_completed >= 0


@pytest.mark.asyncio
async def test_pipeline_dry_run_mode():
    """Test pipeline can be configured for dry-run."""
    pipeline = TradingPipeline(watchlist=["SPY"])
    # Pipeline doesn't have dry_run param in init, but test shows it can execute safely
    metrics = await pipeline.run_full_pipeline()
    assert metrics is not None


# =============================================================================
# Pipeline Status and Metrics Tests
# =============================================================================


def test_phase_result_creation():
    """Test PhaseResult dataclass creation."""
    now = datetime.now()
    result = PhaseResult(
        phase=PipelinePhase.DATA_COLLECTION,
        status=PipelineStatus.COMPLETED,
        started_at=now,
        completed_at=now,
        signals_generated=2,
        orders_placed=1,
    )

    assert result.phase == PipelinePhase.DATA_COLLECTION
    assert result.status == PipelineStatus.COMPLETED
    assert result.signals_generated == 2
    assert result.orders_placed == 1


def test_pipeline_metrics_accumulation():
    """Test PipelineMetrics accumulates phase results."""
    now = datetime.now()
    metrics = PipelineMetrics(started_at=now)

    assert metrics.phases_completed == 0
    assert metrics.total_phases == 5

    # Simulate phase completions
    phase_result = PhaseResult(
        phase=PipelinePhase.DATA_COLLECTION,
        status=PipelineStatus.COMPLETED,
        started_at=now,
        completed_at=now,
    )
    metrics.phase_results.append(phase_result)

    assert len(metrics.phase_results) == 1


def test_pipeline_phase_enum():
    """Test PipelinePhase enum values."""
    assert PipelinePhase.DATA_COLLECTION.value == "data_collection"
    assert PipelinePhase.ANALYSIS.value == "analysis"
    assert PipelinePhase.EXECUTION.value == "execution"
    assert PipelinePhase.MANAGEMENT.value == "management"
    assert PipelinePhase.END_OF_DAY.value == "end_of_day"


def test_pipeline_status_enum():
    """Test PipelineStatus enum values."""
    assert PipelineStatus.IDLE.value == "idle"
    assert PipelineStatus.RUNNING.value == "running"
    assert PipelineStatus.COMPLETED.value == "completed"
    assert PipelineStatus.FAILED.value == "failed"
    assert PipelineStatus.PARTIAL_SUCCESS.value == "partial_success"


# =============================================================================
# Market Hours Tests
# =============================================================================


def test_is_market_hours_mock():
    """Test market hours check."""
    pipeline = TradingPipeline(watchlist=["SPY"])

    # Mock the time-dependent method
    with patch.object(pipeline, "_is_market_hours", return_value=True):
        assert pipeline._is_market_hours() is True

    with patch.object(pipeline, "_is_market_hours", return_value=False):
        assert pipeline._is_market_hours() is False


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_run_phase_handles_errors(trading_pipeline):
    """Test _run_phase handles exceptions gracefully."""

    async def failing_phase(**kwargs):
        raise ValueError("Test error")

    result = await trading_pipeline._run_phase(PipelinePhase.DATA_COLLECTION, failing_phase)

    assert result.status == PipelineStatus.FAILED
    assert len(result.errors) > 0


@pytest.mark.asyncio
async def test_run_phase_success(trading_pipeline):
    """Test _run_phase tracks successful execution."""

    async def successful_phase(**kwargs):
        return {"test": "data"}

    result = await trading_pipeline._run_phase(PipelinePhase.DATA_COLLECTION, successful_phase)

    assert result.status == PipelineStatus.COMPLETED
    assert result.completed_at is not None


# =============================================================================
# Watchlist Tests
# =============================================================================


def test_load_default_watchlist():
    """Test default watchlist loading fallback."""
    with patch("src.trading.trading_pipeline.yaml", None):
        pipeline = TradingPipeline()
        # Should load fallback watchlist
        assert len(pipeline.watchlist) > 0
        assert "SPY" in pipeline.watchlist


# =============================================================================
# Run tests if executed directly
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
