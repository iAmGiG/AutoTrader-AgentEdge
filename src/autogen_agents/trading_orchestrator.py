#!/usr/bin/env python3
"""
TradingOrchestrator - Multi-Agent Coordination and Workflow Management

Coordinates all trading agents (Scanner, Voter, Risk, Executor) and manages
the end-to-end trading workflow with human-in-loop integration.

Issue #389: TradingOrchestrator - Multi-Agent Coordination and Workflow
Refactored: Issue #442 - Extract state management and reporting

Key Features:
1. Workflow Management - Morning routine, continuous monitoring, evening summary
2. State Management - Delegated to WorkflowStateManager
3. Human-in-Loop Modes - CONFIRM (human approval) vs AUTO (autonomous)
4. Error Recovery - Retry logic, graceful failure handling
5. Agent Health Checks - Lifecycle management, health monitoring
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config_defaults.trading_config import TradingConfig

from src.autogen_agents.agent_bus import AgentMessage, EventType, get_agent_bus
from src.autogen_agents.agent_factory import AgentType, get_agent_factory
from src.autogen_agents.workflow_reporter import WorkflowReporter
from src.autogen_agents.workflow_state_manager import WorkflowPhase, WorkflowStateManager
from src.utils.date_utils import get_datetime_now, now_iso

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Trading execution modes for human-in-loop control."""

    CONFIRM = "confirm"  # Human must approve each trade
    AUTO = "auto"  # Autonomous execution (within risk limits)
    PAPER = "paper"  # Paper trading only, no real execution
    DISABLED = "disabled"  # Trading disabled


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

        # State management (extracted component)
        self._state_manager = WorkflowStateManager(state_dir=state_dir)

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
            self._state_manager.recover_state()

        logger.info("TradingOrchestrator initialized:")
        logger.info(f"  Execution Mode: {execution_mode.value}")
        logger.info(f"  Initial Capital: ${initial_capital:,.2f}")
        logger.info(f"  State Directory: {self._state_manager.state_dir}")

    # =========================================================================
    # Properties for backward compatibility
    # =========================================================================

    @property
    def workflow_state(self):
        """Access workflow state (backward compatibility)."""
        return self._state_manager.workflow_state

    @property
    def state_dir(self) -> Path:
        """Access state directory (backward compatibility)."""
        return self._state_manager.state_dir

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
            start = time.time()
            agent = self._get_agent(agent_type)

            # Simple health check - verify agent has expected methods
            if hasattr(agent, "name"):
                _ = agent.name

            health.response_time_ms = (time.time() - start) * 1000
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

        self._state_manager.update_state(WorkflowPhase.SCANNING, started_at=now_iso())

        try:
            # Step 1: Scan for opportunities
            print("🌅 Starting Morning Routine...")
            print("   📊 Phase 1: Scanning markets...")

            scan_result_list = self._execute_with_retry(
                lambda: self.scanner.scan_market(symbols),
                "market_scan",
            )

            scan_results = {r.symbol: r.to_dict() for r in scan_result_list}
            self.workflow_state.symbols_scanned = [r.symbol for r in scan_result_list]
            self.workflow_state.opportunities_found = scan_results
            self._state_manager.save_state()

            # Step 2: Analyze signals
            self._state_manager.update_state(WorkflowPhase.ANALYZING)
            print("   🎯 Phase 2: Analyzing trading signals...")

            analysis_results = self._analyze_scan_results(scan_result_list)
            self.workflow_state.signals_analyzed = analysis_results
            self._state_manager.save_state()

            # Step 3: Risk validation
            self._state_manager.update_state(WorkflowPhase.RISK_CHECKING)
            print("   🛡️  Phase 3: Validating risk parameters...")

            account_status = self.executor.get_account_status()
            current_positions = self.executor.get_positions().get("active_positions", [])
            validated_trades = self._validate_trades(
                analysis_results, account_status, current_positions
            )

            self.workflow_state.risk_validated = validated_trades
            self._state_manager.save_state()

            # Step 4: Handle execution based on mode
            execution_results = self._handle_execution(validated_trades, account_status)

            # Step 5: Generate report
            self._state_manager.update_state(WorkflowPhase.REPORTING)
            print("   📝 Phase 5: Generating report...")

            report = WorkflowReporter.generate_workflow_report(
                self.execution_mode.value,
                scan_results,
                analysis_results,
                validated_trades,
                execution_results,
            )

            self._state_manager.update_state(WorkflowPhase.IDLE)
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
            self._state_manager.update_state(WorkflowPhase.ERROR)
            self._state_manager.record_error("morning_routine", "workflow", str(e))
            logger.error(f"Morning routine failed: {e}")
            return {"error": str(e), "timestamp": now_iso()}

    def _analyze_scan_results(self, scan_result_list: list) -> Dict[str, Any]:
        """Analyze scan results and generate analysis dict."""
        analysis_results = {}
        for scan_result in scan_result_list:
            symbol = scan_result.symbol
            if scan_result.error:
                analysis_results[symbol] = {"error": scan_result.error}
                continue

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
        return analysis_results

    def _validate_trades(
        self,
        analysis_results: Dict[str, Any],
        account_status: Dict[str, Any],
        current_positions: list,
    ) -> Dict[str, Any]:
        """Validate trades through risk agent."""
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
                    self._state_manager.record_error("risk_validation", symbol, str(e))

        return validated_trades

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
        self._state_manager.update_state(WorkflowPhase.MONITORING)

        start_time = get_datetime_now()
        end_time = start_time + timedelta(hours=duration_hours) if duration_hours else None

        while not self._shutdown_requested:
            if end_time and get_datetime_now() >= end_time:
                print("⏰ Monitoring duration reached, stopping...")
                break

            try:
                result = self.monitor_positions()

                if result.get("exit_recommendations"):
                    for symbol, rec in result["exit_recommendations"].items():
                        if rec.get("should_exit"):
                            self._notify(
                                f"Exit signal for {symbol}: {rec.get('reason', 'Unknown')}"
                            )

                for exit in result.get("automatic_exits", []):
                    self._notify(
                        f"Position closed: {exit['symbol']} - {exit.get('reason', 'Triggered')}"
                    )

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                self._state_manager.record_error("monitoring", "continuous", str(e))

            time.sleep(interval_minutes * 60)

        self._state_manager.update_state(WorkflowPhase.IDLE)
        print("✅ Continuous Monitoring Stopped")

    def monitor_positions(self) -> Dict[str, Any]:
        """Monitor existing positions for exit signals."""
        positions_info = self.executor.get_positions()
        active_positions = positions_info.get("active_positions", [])

        if not active_positions:
            return {
                "message": "No active positions to monitor",
                "account_status": self.executor.get_account_status(),
                "timestamp": now_iso(),
            }

        # Fetch current prices
        current_prices = {}
        position_symbols = [p["symbol"] for p in active_positions]
        try:
            scan_results = self.scanner.scan_market(position_symbols)
            for result in scan_results:
                if result.current_price > 0:
                    current_prices[result.symbol] = result.current_price
        except Exception as e:
            logger.warning(f"Failed to scan for current prices: {e}")

        update_result = self.executor.update_positions(current_prices)

        # Evaluate exit signals
        exit_recommendations = {}
        for position in active_positions:
            symbol = position["symbol"]
            if symbol in [e.get("symbol") for e in update_result.get("triggered_exits", [])]:
                continue

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
        """Generate end-of-day summary report."""
        print("🌙 Generating Evening Summary...")

        account_status = self.executor.get_account_status()
        positions = self.executor.get_positions()

        workflow_stats = self._state_manager.get_state_summary()

        summary = WorkflowReporter.generate_evening_summary(
            account_status,
            positions,
            workflow_stats,
            {
                k.value: {"is_healthy": v.is_healthy, "error_count": v.error_count}
                for k, v in self._agent_health.items()
            },
        )
        summary["timestamp"] = now_iso()

        # Reset daily counters
        self._state_manager.reset_state()

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
            self._state_manager.update_state(WorkflowPhase.AWAITING_APPROVAL)
            self._state_manager.set_pending_approvals(approved_trades)

            print("   ⏳ Phase 4: Awaiting human approval...")
            return {
                "status": "awaiting_approval",
                "pending_trades": list(approved_trades.keys()),
                "message": "Trades queued for human approval",
            }

        elif self.execution_mode in [ExecutionMode.AUTO, ExecutionMode.PAPER]:
            self._state_manager.update_state(WorkflowPhase.EXECUTING)
            print("   ⚡ Phase 4: Executing approved trades...")

            execution_results = {}
            for symbol, trade_data in approved_trades.items():
                result = self._execute_trade(symbol, trade_data)
                execution_results[symbol] = result

                if result.get("success"):
                    self._state_manager.add_executed_trade(result)
                else:
                    self._state_manager.add_failed_trade(result)

            return {"status": "executed", "results": execution_results}

        return {"status": "unknown", "message": f"Unknown mode: {self.execution_mode}"}

    def approve_trade(self, symbol: str) -> Dict[str, Any]:
        """Approve a pending trade (CONFIRM mode)."""
        trade_data = self._state_manager.pop_pending_approval(symbol)
        if not trade_data:
            return {"error": f"No pending approval for {symbol}"}

        result = self._execute_trade(symbol, trade_data)

        if result.get("success"):
            self._state_manager.add_executed_trade(result)
        else:
            self._state_manager.add_failed_trade(result)

        return result

    def reject_trade(self, symbol: str, reason: str = "User rejected") -> Dict[str, Any]:
        """Reject a pending trade (CONFIRM mode)."""
        trade_data = self._state_manager.pop_pending_approval(symbol)
        if not trade_data:
            return {"error": f"No pending approval for {symbol}"}

        return {
            "symbol": symbol,
            "status": "rejected",
            "reason": reason,
            "timestamp": now_iso(),
        }

    def get_pending_approvals(self) -> Dict[str, Any]:
        """Get all trades pending human approval."""
        return self._state_manager.get_pending_approvals()

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
    # State Management (delegated to WorkflowStateManager)
    # =========================================================================

    def reset_state(self):
        """Reset workflow state."""
        self._state_manager.reset_state()

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
                self._state_manager.increment_retry()
                logger.warning(f"{operation_name} failed (attempt {attempt + 1}/{retries}): {e}")

                if attempt < retries - 1:
                    time.sleep(self.RETRY_DELAY_SECONDS * (attempt + 1))
                else:
                    raise

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
    # Reporting (delegated to WorkflowReporter)
    # =========================================================================

    def generate_status_report(self) -> str:
        """Generate current status report."""
        account = self.executor.get_account_status()
        positions = self.executor.get_positions()

        return WorkflowReporter.generate_status_report(
            self.execution_mode.value,
            self.trading_enabled,
            self.workflow_state.phase.value,
            account,
            positions,
            self._agent_health,
            self._state_manager.get_pending_approvals(),
        )

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def shutdown(self):
        """Gracefully shutdown the orchestrator."""
        print("🔄 Shutting down TradingOrchestrator...")
        self._shutdown_requested = True
        self.trading_enabled = False

        self._state_manager.save_state()

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
