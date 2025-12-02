"""
Workflow State Manager - persistence and recovery for trading workflows.

Handles state persistence, recovery, and management for TradingOrchestrator.
Extracted from trading_orchestrator.py (Issue #442).
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


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


class WorkflowStateManager:
    """
    Manages workflow state persistence and recovery.

    Handles:
    - State updates
    - Persistence to JSON
    - Recovery from disk
    - Error recording
    """

    DEFAULT_STATE_FILE = "orchestrator_state.json"

    def __init__(self, state_dir: Optional[str] = None, state_file: Optional[str] = None):
        """
        Initialize state manager.

        Args:
            state_dir: Directory for state files (default: ./state)
            state_file: State file name (default: orchestrator_state.json)
        """
        self.state_dir = Path(state_dir or "./state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = state_file or self.DEFAULT_STATE_FILE
        self.workflow_state = WorkflowState()

    @property
    def state_path(self) -> Path:
        """Get full path to state file."""
        return self.state_dir / self.state_file

    def update_state(self, phase: WorkflowPhase, **kwargs) -> None:
        """
        Update workflow state.

        Args:
            phase: New workflow phase
            **kwargs: Additional state attributes to update
        """
        self.workflow_state.phase = phase
        self.workflow_state.last_updated = now_iso()

        for key, value in kwargs.items():
            if hasattr(self.workflow_state, key):
                setattr(self.workflow_state, key, value)

        self.save_state()

    def save_state(self) -> bool:
        """
        Persist workflow state to disk.

        Returns:
            True if saved successfully
        """
        try:
            with open(self.state_path, "w") as f:
                json.dump(self.workflow_state.to_dict(), f, indent=2, default=str)
            return True
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
            return False

    def recover_state(self) -> bool:
        """
        Recover workflow state from disk.

        Returns:
            True if recovered successfully
        """
        try:
            if self.state_path.exists():
                with open(self.state_path, "r") as f:
                    data = json.load(f)
                self.workflow_state = WorkflowState.from_dict(data)
                logger.info(f"Recovered state: phase={self.workflow_state.phase.value}")
                return True
        except Exception as e:
            logger.warning(f"Failed to recover state: {e}")
            self.workflow_state = WorkflowState()
        return False

    def reset_state(self) -> None:
        """Reset workflow state to initial state."""
        self.workflow_state = WorkflowState()
        self.save_state()
        logger.info("Workflow state reset")

    def record_error(self, phase: str, symbol: str, error: str) -> None:
        """
        Record an error in workflow state.

        Args:
            phase: Workflow phase when error occurred
            symbol: Symbol associated with error
            error: Error message
        """
        self.workflow_state.errors.append(
            {
                "phase": phase,
                "symbol": symbol,
                "error": error,
                "timestamp": now_iso(),
            }
        )

    def increment_retry(self) -> int:
        """
        Increment retry count.

        Returns:
            New retry count
        """
        self.workflow_state.retry_count += 1
        return self.workflow_state.retry_count

    def add_executed_trade(self, trade_result: Dict[str, Any]) -> None:
        """Add a successfully executed trade to state."""
        self.workflow_state.trades_executed.append(trade_result)
        self.save_state()

    def add_failed_trade(self, trade_result: Dict[str, Any]) -> None:
        """Add a failed trade to state."""
        self.workflow_state.trades_failed.append(trade_result)
        self.save_state()

    def set_pending_approvals(self, approvals: Dict[str, Any]) -> None:
        """Set pending approvals for human review."""
        self.workflow_state.pending_approvals = approvals
        self.save_state()

    def pop_pending_approval(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Remove and return a pending approval.

        Args:
            symbol: Symbol to approve

        Returns:
            Trade data or None if not found
        """
        trade_data = self.workflow_state.pending_approvals.pop(symbol, None)
        if trade_data:
            self.save_state()
        return trade_data

    def get_pending_approvals(self) -> Dict[str, Any]:
        """Get all pending approvals."""
        return self.workflow_state.pending_approvals.copy()

    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get summary of current state.

        Returns:
            Dictionary with key state metrics
        """
        return {
            "phase": self.workflow_state.phase.value,
            "symbols_scanned": len(self.workflow_state.symbols_scanned),
            "trades_executed": len(self.workflow_state.trades_executed),
            "trades_failed": len(self.workflow_state.trades_failed),
            "pending_approvals": len(self.workflow_state.pending_approvals),
            "errors": len(self.workflow_state.errors),
            "retry_count": self.workflow_state.retry_count,
            "last_updated": self.workflow_state.last_updated,
        }
