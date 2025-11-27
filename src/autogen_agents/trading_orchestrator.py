#!/usr/bin/env python3
"""
TradingOrchestrator - Multi-Agent Coordination and Workflow Management

Coordinates all trading agents (Scanner, Voter, Risk, Executor) and manages
the end-to-end trading workflow with human-in-loop integration.

Issue #389: TradingOrchestrator - Multi-Agent Coordination and Workflow

Key Features:
1. Workflow Management - Morning routine, continuous monitoring, evening summary
2. State Management - Workflow progress tracking, persistence, recovery
3. Human-in-Loop Modes - CONFIRM (human approval) vs AUTO (autonomous)
4. Error Recovery - Retry logic, graceful failure handling
5. Agent Health Checks - Lifecycle management, health monitoring
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config_defaults.trading_config import TradingConfig

from src.autogen_agents.agent_bus import AgentMessage, EventType, get_agent_bus
from src.autogen_agents.agent_factory import AgentType, get_agent_factory
from src.utils.date_utils import get_datetime_now, now_iso

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Trading execution modes for human-in-loop control."""

    CONFIRM = "confirm"  # Human must approve each trade
    AUTO = "auto"  # Autonomous execution (within risk limits)
    PAPER = "paper"  # Paper trading only, no real execution
    DISABLED = "disabled"  # Trading disabled


class WorkflowPhase(Enum):
    """Phases in the trading workflow."""

    IDLE = "idle"
    SCANNING = "scanning"
    ANALYZING = "analyzing"
    RISK_CHECKING = "risk_checking"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    REPORTING = "reporting"
    ERROR = "error"


@dataclass
class WorkflowState:
    """Tracks current workflow progress for recovery."""

    phase: WorkflowPhase = WorkflowPhase.IDLE
    started_at: Optional[str] = None
    last_updated: str = field(default_factory=now_iso)

    # Scan results
    symbols_scanned: List[str] = field(default_factory=list)
    opportunities_found: Dict[str, Any] = field(default_factory=dict)

    # Analysis results
    signals_analyzed: Dict[str, Any] = field(default_factory=dict)
    risk_validated: Dict[str, Any] = field(default_factory=dict)

    # Pending human approval
    pending_approvals: Dict[str, Any] = field(default_factory=dict)

    # Execution tracking
    trades_executed: List[Dict[str, Any]] = field(default_factory=list)
    trades_failed: List[Dict[str, Any]] = field(default_factory=list)

    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for persistence."""
        return {
            "phase": self.phase.value,
            "started_at": self.started_at,
            "last_updated": self.last_updated,
            "symbols_scanned": self.symbols_scanned,
            "opportunities_found": self.opportunities_found,
            "signals_analyzed": self.signals_analyzed,
            "risk_validated": self.risk_validated,
            "pending_approvals": self.pending_approvals,
            "trades_executed": self.trades_executed,
            "trades_failed": self.trades_failed,
            "errors": self.errors,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowState":
        """Restore from dictionary."""
        state = cls()
        state.phase = WorkflowPhase(data.get("phase", "idle"))
        state.started_at = data.get("started_at")
        state.last_updated = data.get("last_updated", now_iso())
        state.symbols_scanned = data.get("symbols_scanned", [])
        state.opportunities_found = data.get("opportunities_found", {})
        state.signals_analyzed = data.get("signals_analyzed", {})
        state.risk_validated = data.get("risk_validated", {})
        state.pending_approvals = data.get("pending_approvals", {})
        state.trades_executed = data.get("trades_executed", [])
        state.trades_failed = data.get("trades_failed", [])
        state.errors = data.get("errors", [])
        state.retry_count = data.get("retry_count", 0)
        return state


@dataclass
class AgentHealth:
    """Health status for an agent."""

    agent_type: AgentType
    is_healthy: bool = True
    last_check: str = field(default_factory=now_iso)
    error_count: int = 0
    last_error: Optional[str] = None
    response_time_ms: float = 0.0


class TradingOrchestrator:
    """
    Multi-agent coordination orchestrator for trading workflows.

    Manages the full trading lifecycle from market scanning through execution,
    with support for human-in-loop approval and autonomous operation modes.
    """

    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 5
    STATE_FILE = "orchestrator_state.json"

    def __init__(
        self,
        initial_capital: float = 100000,
        execution_mode: ExecutionMode = ExecutionMode.CONFIRM,
        state_dir: Optional[str] = None,
        auto_recover: bool = True,
    ):
        """
        Initialize TradingOrchestrator.

        Args:
            initial_capital: Starting capital for paper trading
            execution_mode: How trades are executed (CONFIRM, AUTO, PAPER, DISABLED)
            state_dir: Directory for state persistence (default: ./state)
            auto_recover: Automatically recover from saved state on init
        """
        self.config = TradingConfig()
        self.initial_capital = initial_capital
        self.execution_mode = execution_mode

        # State management
        self.state_dir = Path(state_dir or "./state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.workflow_state = WorkflowState()

        # Get factory and bus singletons
        self._factory = get_agent_factory()
        self._bus = get_agent_bus()

        # Agent instances (lazy loaded)
        self._agents: Dict[AgentType, Any] = {}
        self._agent_health: Dict[AgentType, AgentHealth] = {}

        # Workflow control
        self.trading_enabled = True
        self._shutdown_requested = False

        # Human approval callbacks
        self._approval_callback: Optional[Callable] = None
        self._notification_callback: Optional[Callable] = None

        # Event subscriptions
        self._setup_event_subscriptions()

        # Auto-recover if enabled
        if auto_recover:
            self._recover_state()

        logger.info("TradingOrchestrator initialized:")
        logger.info(f"  Execution Mode: {execution_mode.value}")
        logger.info(f"  Initial Capital: ${initial_capital:,.2f}")
        logger.info(f"  State Directory: {self.state_dir}")

    # =========================================================================
    # Agent Management
    # =========================================================================

    def _get_agent(self, agent_type: AgentType) -> Any:
        """Get or create an agent instance."""
        if agent_type not in self._agents:
            try:
                config_override = {}
                if agent_type == AgentType.EXECUTOR:
                    config_override = {"extra_config": {"initial_capital": self.initial_capital}}

                instance = self._factory.create(agent_type, config_override=config_override)
                self._agents[agent_type] = instance.agent
                self._agent_health[agent_type] = AgentHealth(agent_type=agent_type)
                logger.info(f"Agent created: {agent_type.value}")
            except Exception as e:
                logger.error(f"Failed to create agent {agent_type.value}: {e}")
                raise

        return self._agents[agent_type]

    @property
    def scanner(self):
        """Get ScannerAgent."""
        return self._get_agent(AgentType.SCANNER)

    @property
    def voter(self):
        """Get VoterAgent."""
        return self._get_agent(AgentType.VOTER)

    @property
    def risk(self):
        """Get RiskAgent."""
        return self._get_agent(AgentType.RISK)

    @property
    def executor(self):
        """Get ExecutorAgent."""
        return self._get_agent(AgentType.EXECUTOR)

    def check_agent_health(self, agent_type: AgentType) -> AgentHealth:
        """Check health of a specific agent."""
        health = self._agent_health.get(agent_type, AgentHealth(agent_type=agent_type))

        try:
            start = datetime.now()
            agent = self._get_agent(agent_type)

            # Simple health check - verify agent has expected methods
            if hasattr(agent, "name"):
                _ = agent.name

            health.response_time_ms = (datetime.now() - start).total_seconds() * 1000
            health.is_healthy = True
            health.last_check = now_iso()

        except Exception as e:
            health.is_healthy = False
            health.error_count += 1
            health.last_error = str(e)
            health.last_check = now_iso()

        self._agent_health[agent_type] = health
        return health

    def get_all_agent_health(self) -> Dict[str, AgentHealth]:
        """Check health of all agents."""
        return {
            agent_type.value: self.check_agent_health(agent_type)
            for agent_type in [
                AgentType.SCANNER,
                AgentType.VOTER,
                AgentType.RISK,
                AgentType.EXECUTOR,
            ]
        }

    # =========================================================================
    # Workflow Execution
    # =========================================================================

    def run_morning_routine(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute the morning trading routine.

        Workflow:
        1. ScannerAgent scans watchlist for opportunities
        2. VoterAgent analyzes top candidates with MACD+RSI
        3. RiskAgent validates position sizes and portfolio risk
        4. Present to human for approval (CONFIRM mode) or execute (AUTO mode)
        5. Generate summary report

        Args:
            symbols: Symbols to scan, uses default watchlist if None

        Returns:
            Workflow results including recommendations and execution status
        """
        if not self.trading_enabled:
            return {"error": "Trading is disabled", "timestamp": now_iso()}

        self._update_state(WorkflowPhase.SCANNING, started_at=now_iso())

        try:
            # Step 1: Scan for opportunities
            print("🌅 Starting Morning Routine...")
            print("   📊 Phase 1: Scanning markets...")

            # ScannerAgent.scan_market() returns List[ScanResult]
            scan_result_list = self._execute_with_retry(
                lambda: self.scanner.scan_market(symbols),
                "market_scan",
            )

            # Convert to dict for workflow state
            scan_results = {r.symbol: r.to_dict() for r in scan_result_list}
            self.workflow_state.symbols_scanned = [r.symbol for r in scan_result_list]
            self.workflow_state.opportunities_found = scan_results
            self._save_state()

            # Step 2: Analyze signals with VoterAgent
            # ScannerAgent already provides MACD+RSI analysis in ScanResult
            # VoterAgent can provide additional evaluation if needed
            self._update_state(WorkflowPhase.ANALYZING)
            print("   🎯 Phase 2: Analyzing trading signals...")

            analysis_results = {}
            for scan_result in scan_result_list:
                symbol = scan_result.symbol
                if scan_result.error:
                    analysis_results[symbol] = {"error": scan_result.error}
                    continue

                # Use ScanResult data directly - it already has MACD+RSI analysis
                analysis_results[symbol] = {
                    "symbol": symbol,
                    "decision": (
                        f"ENTER_{scan_result.action}" if scan_result.action != "HOLD" else "HOLD"
                    ),
                    "action": scan_result.action,
                    "confidence": scan_result.confidence,
                    "signal_type": scan_result.signal_type,
                    "current_price": scan_result.current_price,
                    "macd_signal": scan_result.macd_signal,
                    "macd_histogram": scan_result.macd_histogram,
                    "rsi_value": scan_result.rsi_value,
                    "rsi_signal": scan_result.rsi_signal,
                    "ranking_score": scan_result.ranking_score,
                }

            self.workflow_state.signals_analyzed = analysis_results
            self._save_state()

            # Step 3: Risk validation
            self._update_state(WorkflowPhase.RISK_CHECKING)
            print("   🛡️  Phase 3: Validating risk parameters...")

            account_status = self.executor.get_account_status()
            current_positions = self.executor.get_positions().get("active_positions", [])

            validated_trades = {}
            for symbol, analysis in analysis_results.items():
                if analysis.get("decision", "").startswith("ENTER"):
                    try:
                        trade_proposal = {
                            "symbol": symbol,
                            "entry_price": analysis.get("current_price", 0),
                            "stop_price": analysis.get("stop_loss", 0),
                            "target_price": analysis.get("take_profit", 0),
                            "action": "BUY",
                            "confidence": analysis.get("confidence", 0.5),
                        }

                        risk_result = self.risk.validate_trade(
                            trade_proposal,
                            account_status.get("total_value", self.initial_capital),
                            current_positions,
                        )

                        validated_trades[symbol] = {
                            "analysis": analysis,
                            "risk_validation": risk_result,
                            "approved": risk_result.get("approved", False),
                        }
                    except Exception as e:
                        validated_trades[symbol] = {"error": str(e)}
                        self._record_error("risk_validation", symbol, str(e))

            self.workflow_state.risk_validated = validated_trades
            self._save_state()

            # Step 4: Handle execution based on mode
            execution_results = self._handle_execution(validated_trades, account_status)

            # Step 5: Generate report
            self._update_state(WorkflowPhase.REPORTING)
            print("   📝 Phase 5: Generating report...")

            report = self._generate_workflow_report(
                scan_results, analysis_results, validated_trades, execution_results
            )

            self._update_state(WorkflowPhase.IDLE)
            print("✅ Morning Routine Complete!")

            return {
                "success": True,
                "scan_results": scan_results,
                "analysis_results": analysis_results,
                "validated_trades": validated_trades,
                "execution_results": execution_results,
                "report": report,
                "timestamp": now_iso(),
            }

        except Exception as e:
            self._update_state(WorkflowPhase.ERROR)
            self._record_error("morning_routine", "workflow", str(e))
            logger.error(f"Morning routine failed: {e}")
            return {"error": str(e), "timestamp": now_iso()}

    def run_continuous_monitoring(
        self, interval_minutes: int = 15, duration_hours: Optional[float] = None
    ):
        """
        Run continuous position monitoring.

        Args:
            interval_minutes: Minutes between checks
            duration_hours: How long to run (None = until shutdown)
        """
        print(f"📈 Starting Continuous Monitoring (every {interval_minutes} min)...")
        self._update_state(WorkflowPhase.MONITORING)

        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours) if duration_hours else None

        while not self._shutdown_requested:
            if end_time and datetime.now() >= end_time:
                print("⏰ Monitoring duration reached, stopping...")
                break

            try:
                result = self.monitor_positions()

                # Check for exit signals
                if result.get("exit_recommendations"):
                    for symbol, rec in result["exit_recommendations"].items():
                        if rec.get("should_exit"):
                            self._notify(
                                f"Exit signal for {symbol}: {rec.get('reason', 'Unknown')}"
                            )

                # Check for stop/target triggers
                for exit in result.get("automatic_exits", []):
                    self._notify(
                        f"Position closed: {exit['symbol']} - {exit.get('reason', 'Triggered')}"
                    )

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                self._record_error("monitoring", "continuous", str(e))

            # Wait for next interval
            import time

            time.sleep(interval_minutes * 60)

        self._update_state(WorkflowPhase.IDLE)
        print("✅ Continuous Monitoring Stopped")

    def monitor_positions(self) -> Dict[str, Any]:
        """
        Monitor existing positions for exit signals.

        Returns:
            Position monitoring results with exit recommendations
        """
        positions_info = self.executor.get_positions()
        active_positions = positions_info.get("active_positions", [])

        if not active_positions:
            return {
                "message": "No active positions to monitor",
                "account_status": self.executor.get_account_status(),
                "timestamp": now_iso(),
            }

        # Fetch current prices by scanning position symbols
        current_prices = {}
        position_symbols = [p["symbol"] for p in active_positions]
        try:
            # Use scanner to get current prices
            scan_results = self.scanner.scan_market(position_symbols)
            for result in scan_results:
                if result.current_price > 0:
                    current_prices[result.symbol] = result.current_price
        except Exception as e:
            logger.warning(f"Failed to scan for current prices: {e}")

        # Update positions
        update_result = self.executor.update_positions(current_prices)

        # Evaluate exit signals
        exit_recommendations = {}
        for position in active_positions:
            symbol = position["symbol"]
            if symbol in [e.get("symbol") for e in update_result.get("triggered_exits", [])]:
                continue  # Already exited

            current_price = current_prices.get(symbol, position["entry_price"])
            try:
                exit_eval = self.voter.evaluate_exit_signal(
                    symbol, position["entry_price"], current_price, "long"
                )
                exit_recommendations[symbol] = exit_eval
            except Exception as e:
                exit_recommendations[symbol] = {"error": str(e)}

        return {
            "automatic_exits": update_result.get("triggered_exits", []),
            "exit_recommendations": exit_recommendations,
            "position_updates": update_result,
            "account_status": update_result.get("account_status", {}),
            "timestamp": now_iso(),
        }

    def run_evening_summary(self) -> Dict[str, Any]:
        """
        Generate end-of-day summary report.

        Returns:
            Summary of day's trading activity
        """
        print("🌙 Generating Evening Summary...")

        account_status = self.executor.get_account_status()
        positions = self.executor.get_positions()

        # Calculate day's P&L
        daily_pnl = account_status.get("realized_pnl", 0)
        unrealized_pnl = account_status.get("unrealized_pnl", 0)

        # Get workflow statistics
        workflow_stats = {
            "symbols_scanned": len(self.workflow_state.symbols_scanned),
            "trades_executed": len(self.workflow_state.trades_executed),
            "trades_failed": len(self.workflow_state.trades_failed),
            "errors": len(self.workflow_state.errors),
        }

        summary = {
            "date": get_datetime_now().strftime("%Y-%m-%d"),
            "account_status": account_status,
            "positions": positions,
            "daily_pnl": daily_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": daily_pnl + unrealized_pnl,
            "workflow_stats": workflow_stats,
            "agent_health": {
                k: {"is_healthy": v.is_healthy, "error_count": v.error_count}
                for k, v in self._agent_health.items()
            },
            "timestamp": now_iso(),
        }

        # Reset daily counters
        self.workflow_state = WorkflowState()
        self._save_state()

        print("✅ Evening Summary Complete")
        return summary

    # =========================================================================
    # Execution Handling
    # =========================================================================

    def _handle_execution(
        self, validated_trades: Dict[str, Any], account_status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle trade execution based on execution mode."""
        if self.execution_mode == ExecutionMode.DISABLED:
            return {"status": "disabled", "message": "Trading is disabled"}

        approved_trades = {
            symbol: data for symbol, data in validated_trades.items() if data.get("approved", False)
        }

        if not approved_trades:
            return {"status": "no_trades", "message": "No trades approved by risk"}

        if self.execution_mode == ExecutionMode.CONFIRM:
            # Queue for human approval
            self._update_state(WorkflowPhase.AWAITING_APPROVAL)
            self.workflow_state.pending_approvals = approved_trades
            self._save_state()

            print("   ⏳ Phase 4: Awaiting human approval...")
            return {
                "status": "awaiting_approval",
                "pending_trades": list(approved_trades.keys()),
                "message": "Trades queued for human approval",
            }

        elif self.execution_mode in [ExecutionMode.AUTO, ExecutionMode.PAPER]:
            # Execute automatically
            self._update_state(WorkflowPhase.EXECUTING)
            print("   ⚡ Phase 4: Executing approved trades...")

            execution_results = {}
            for symbol, trade_data in approved_trades.items():
                result = self._execute_trade(symbol, trade_data)
                execution_results[symbol] = result

                if result.get("success"):
                    self.workflow_state.trades_executed.append(result)
                else:
                    self.workflow_state.trades_failed.append(result)

            self._save_state()
            return {
                "status": "executed",
                "results": execution_results,
            }

        return {"status": "unknown", "message": f"Unknown mode: {self.execution_mode}"}

    def approve_trade(self, symbol: str) -> Dict[str, Any]:
        """
        Approve a pending trade (CONFIRM mode).

        Args:
            symbol: Symbol to approve

        Returns:
            Execution result
        """
        if symbol not in self.workflow_state.pending_approvals:
            return {"error": f"No pending approval for {symbol}"}

        trade_data = self.workflow_state.pending_approvals.pop(symbol)
        result = self._execute_trade(symbol, trade_data)

        if result.get("success"):
            self.workflow_state.trades_executed.append(result)
        else:
            self.workflow_state.trades_failed.append(result)

        self._save_state()
        return result

    def reject_trade(self, symbol: str, reason: str = "User rejected") -> Dict[str, Any]:
        """
        Reject a pending trade (CONFIRM mode).

        Args:
            symbol: Symbol to reject
            reason: Reason for rejection

        Returns:
            Rejection confirmation
        """
        if symbol not in self.workflow_state.pending_approvals:
            return {"error": f"No pending approval for {symbol}"}

        self.workflow_state.pending_approvals.pop(symbol)
        self._save_state()

        return {
            "symbol": symbol,
            "status": "rejected",
            "reason": reason,
            "timestamp": now_iso(),
        }

    def get_pending_approvals(self) -> Dict[str, Any]:
        """Get all trades pending human approval."""
        return self.workflow_state.pending_approvals.copy()

    def _execute_trade(self, symbol: str, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single trade."""
        try:
            risk_result = trade_data.get("risk_validation", {})
            analysis = trade_data.get("analysis", {})

            order = {
                "symbol": symbol,
                "action": "BUY",
                "shares": risk_result.get("recommended_quantity", 1),
                "price": analysis.get("current_price", 0),
                "stop_loss": analysis.get("stop_loss"),
                "take_profit": analysis.get("take_profit"),
            }

            result = self.executor.execute_trade(order)
            return {
                "symbol": symbol,
                "success": result.get("success", False),
                "order": order,
                "result": result,
                "timestamp": now_iso(),
            }

        except Exception as e:
            return {
                "symbol": symbol,
                "success": False,
                "error": str(e),
                "timestamp": now_iso(),
            }

    # =========================================================================
    # State Management
    # =========================================================================

    def _update_state(self, phase: WorkflowPhase, **kwargs):
        """Update workflow state."""
        self.workflow_state.phase = phase
        self.workflow_state.last_updated = now_iso()

        for key, value in kwargs.items():
            if hasattr(self.workflow_state, key):
                setattr(self.workflow_state, key, value)

        self._save_state()

    def _save_state(self):
        """Persist workflow state to disk."""
        try:
            state_path = self.state_dir / self.STATE_FILE
            with open(state_path, "w") as f:
                json.dump(self.workflow_state.to_dict(), f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    def _recover_state(self):
        """Recover workflow state from disk."""
        try:
            state_path = self.state_dir / self.STATE_FILE
            if state_path.exists():
                with open(state_path, "r") as f:
                    data = json.load(f)
                self.workflow_state = WorkflowState.from_dict(data)
                logger.info(f"Recovered state: phase={self.workflow_state.phase.value}")
        except Exception as e:
            logger.warning(f"Failed to recover state: {e}")
            self.workflow_state = WorkflowState()

    def reset_state(self):
        """Reset workflow state."""
        self.workflow_state = WorkflowState()
        self._save_state()
        logger.info("Workflow state reset")

    # =========================================================================
    # Error Handling & Retry
    # =========================================================================

    def _execute_with_retry(
        self,
        operation: Callable,
        operation_name: str,
        max_retries: Optional[int] = None,
    ) -> Any:
        """Execute an operation with retry logic."""
        retries = max_retries or self.MAX_RETRIES

        for attempt in range(retries):
            try:
                return operation()
            except Exception as e:
                self.workflow_state.retry_count += 1
                logger.warning(f"{operation_name} failed (attempt {attempt + 1}/{retries}): {e}")

                if attempt < retries - 1:
                    import time

                    time.sleep(self.RETRY_DELAY_SECONDS * (attempt + 1))
                else:
                    raise

    def _record_error(self, phase: str, symbol: str, error: str):
        """Record an error in workflow state."""
        self.workflow_state.errors.append(
            {
                "phase": phase,
                "symbol": symbol,
                "error": error,
                "timestamp": now_iso(),
            }
        )

    def _count_entry_signals(self, analysis_results: Dict[str, Any]) -> int:
        """Count entry signals in analysis results."""
        return sum(
            1 for r in analysis_results.values() if r.get("decision", "").startswith("ENTER")
        )

    # =========================================================================
    # Event Bus Integration
    # =========================================================================

    def _setup_event_subscriptions(self):
        """Subscribe to key events for monitoring."""

        def log_trade(msg: AgentMessage):
            symbol = msg.symbol or "UNKNOWN"
            logger.info(f"[Orchestrator] Trade executed: {symbol}")

        def log_risk_event(msg: AgentMessage):
            symbol = msg.symbol or "UNKNOWN"
            approved = msg.payload.get("approved", False)
            logger.info(f"[Orchestrator] Risk {'approved' if approved else 'rejected'}: {symbol}")

        self._bus.subscribe("orchestrator", EventType.TRADE_EXECUTED, log_trade)
        self._bus.subscribe("orchestrator", EventType.RISK_VALIDATED, log_risk_event)
        self._bus.subscribe("orchestrator", EventType.RISK_REJECTED, log_risk_event)

    # =========================================================================
    # Human Interface
    # =========================================================================

    def set_approval_callback(self, callback: Callable):
        """Set callback for requesting human approval."""
        self._approval_callback = callback

    def set_notification_callback(self, callback: Callable):
        """Set callback for sending notifications."""
        self._notification_callback = callback

    def _notify(self, message: str):
        """Send notification via callback or print."""
        if self._notification_callback:
            self._notification_callback(message)
        else:
            print(f"🔔 {message}")

    # =========================================================================
    # Reporting
    # =========================================================================

    def _generate_workflow_report(
        self,
        scan_results: Dict,
        analysis_results: Dict,
        validated_trades: Dict,
        execution_results: Dict,
    ) -> str:
        """Generate comprehensive workflow report."""
        lines = [
            "=" * 60,
            "🤖 TRADING WORKFLOW REPORT",
            "=" * 60,
            f"Generated: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Mode: {self.execution_mode.value.upper()}",
            "",
            "📊 SCAN RESULTS:",
            f"  Symbols Scanned: {len(scan_results)}",
            f"  Opportunities Found: {sum(1 for r in scan_results.values() if 'error' not in r)}",
            "",
            "🎯 ANALYSIS RESULTS:",
            f"  Signals Analyzed: {len(analysis_results)}",
            f"  Entry Signals: {self._count_entry_signals(analysis_results)}",
            "",
            "🛡️ RISK VALIDATION:",
            f"  Trades Validated: {len(validated_trades)}",
            f"  Approved: {sum(1 for r in validated_trades.values() if r.get('approved'))}",
            "",
        ]

        # Execution status
        if execution_results.get("status") == "awaiting_approval":
            lines.extend(
                [
                    "⏳ PENDING APPROVAL:",
                    f"  Trades Pending: {len(execution_results.get('pending_trades', []))}",
                ]
            )
        elif execution_results.get("status") == "executed":
            results = execution_results.get("results", {})
            success = sum(1 for r in results.values() if r.get("success"))
            lines.extend(
                [
                    "⚡ EXECUTION RESULTS:",
                    f"  Executed: {success}/{len(results)}",
                ]
            )

        lines.extend(["", "=" * 60])
        return "\n".join(lines)

    def generate_status_report(self) -> str:
        """Generate current status report."""
        account = self.executor.get_account_status()
        positions = self.executor.get_positions()

        lines = [
            "=" * 60,
            "🤖 TRADING ORCHESTRATOR STATUS",
            "=" * 60,
            f"Time: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Phase: {self.workflow_state.phase.value}",
            f"Mode: {self.execution_mode.value}",
            f"Trading Enabled: {'Yes' if self.trading_enabled else 'No'}",
            "",
            "💰 ACCOUNT:",
            f"  Total Value: ${account.get('total_value', 0):,.2f}",
            f"  Available: ${account.get('available_cash', 0):,.2f}",
            f"  P&L: ${account.get('total_return_pct', 0) * 100:.2f}%",
            "",
            f"📊 POSITIONS: {positions.get('total_positions', 0)} active",
            "",
            "🔧 AGENT HEALTH:",
        ]

        for agent_type, health in self._agent_health.items():
            status = "✅" if health.is_healthy else "❌"
            lines.append(f"  {agent_type.value}: {status}")

        if self.workflow_state.pending_approvals:
            lines.extend(
                [
                    "",
                    f"⏳ PENDING APPROVALS: {len(self.workflow_state.pending_approvals)}",
                ]
            )

        lines.append("=" * 60)
        return "\n".join(lines)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def shutdown(self):
        """Gracefully shutdown the orchestrator."""
        print("🔄 Shutting down TradingOrchestrator...")
        self._shutdown_requested = True
        self.trading_enabled = False

        # Save final state
        self._save_state()

        # Unsubscribe from events
        try:
            self._bus.unsubscribe("orchestrator", EventType.TRADE_EXECUTED)
            self._bus.unsubscribe("orchestrator", EventType.RISK_VALIDATED)
            self._bus.unsubscribe("orchestrator", EventType.RISK_REJECTED)
        except Exception:
            pass

        print("✅ Orchestrator shutdown complete")


def create_trading_orchestrator(
    initial_capital: float = 100000,
    execution_mode: str = "confirm",
) -> TradingOrchestrator:
    """Factory function to create a configured TradingOrchestrator."""
    mode = ExecutionMode(execution_mode.lower())
    return TradingOrchestrator(initial_capital=initial_capital, execution_mode=mode)
