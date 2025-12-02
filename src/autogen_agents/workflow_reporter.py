"""
Workflow Reporter - report generation for trading workflows.

Generates comprehensive workflow and status reports.
Extracted from trading_orchestrator.py (Issue #442).
"""

from typing import Any, Dict

from src.utils.date_utils import get_datetime_now


class WorkflowReporter:
    """
    Generate reports for trading workflow status.

    Handles:
    - Workflow summary reports
    - Status reports
    - Position reports
    """

    @staticmethod
    def count_entry_signals(analysis_results: Dict[str, Any]) -> int:
        """Count entry signals in analysis results."""
        return sum(
            1 for r in analysis_results.values() if r.get("decision", "").startswith("ENTER")
        )

    @classmethod
    def generate_workflow_report(
        cls,
        execution_mode: str,
        scan_results: Dict[str, Any],
        analysis_results: Dict[str, Any],
        validated_trades: Dict[str, Any],
        execution_results: Dict[str, Any],
    ) -> str:
        """
        Generate comprehensive workflow report.

        Args:
            execution_mode: Current execution mode (confirm/auto/paper/disabled)
            scan_results: Results from market scanning
            analysis_results: Results from signal analysis
            validated_trades: Risk-validated trades
            execution_results: Results from trade execution

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 60,
            "🤖 TRADING WORKFLOW REPORT",
            "=" * 60,
            f"Generated: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Mode: {execution_mode.upper()}",
            "",
            "📊 SCAN RESULTS:",
            f"  Symbols Scanned: {len(scan_results)}",
            f"  Opportunities Found: {sum(1 for r in scan_results.values() if 'error' not in r)}",
            "",
            "🎯 ANALYSIS RESULTS:",
            f"  Signals Analyzed: {len(analysis_results)}",
            f"  Entry Signals: {cls.count_entry_signals(analysis_results)}",
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

    @classmethod
    def generate_status_report(
        cls,
        execution_mode: str,
        trading_enabled: bool,
        workflow_phase: str,
        account_status: Dict[str, Any],
        positions: Dict[str, Any],
        agent_health: Dict[str, Any],
        pending_approvals: Dict[str, Any],
    ) -> str:
        """
        Generate current status report.

        Args:
            execution_mode: Current execution mode
            trading_enabled: Whether trading is enabled
            workflow_phase: Current workflow phase
            account_status: Account status dict
            positions: Positions info dict
            agent_health: Agent health status dict
            pending_approvals: Pending trade approvals

        Returns:
            Formatted status report string
        """
        lines = [
            "=" * 60,
            "🤖 TRADING ORCHESTRATOR STATUS",
            "=" * 60,
            f"Time: {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Phase: {workflow_phase}",
            f"Mode: {execution_mode}",
            f"Trading Enabled: {'Yes' if trading_enabled else 'No'}",
            "",
            "💰 ACCOUNT:",
            f"  Total Value: ${account_status.get('total_value', 0):,.2f}",
            f"  Available: ${account_status.get('available_cash', 0):,.2f}",
            f"  P&L: ${account_status.get('total_return_pct', 0) * 100:.2f}%",
            "",
            f"📊 POSITIONS: {positions.get('total_positions', 0)} active",
            "",
            "🔧 AGENT HEALTH:",
        ]

        for agent_type, health in agent_health.items():
            status = "✅" if health.is_healthy else "❌"
            lines.append(f"  {agent_type}: {status}")

        if pending_approvals:
            lines.extend(
                [
                    "",
                    f"⏳ PENDING APPROVALS: {len(pending_approvals)}",
                ]
            )

        lines.append("=" * 60)
        return "\n".join(lines)

    @classmethod
    def generate_evening_summary(
        cls,
        account_status: Dict[str, Any],
        positions: Dict[str, Any],
        workflow_stats: Dict[str, Any],
        agent_health: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate end-of-day summary.

        Args:
            account_status: Account status dict
            positions: Positions info
            workflow_stats: Workflow statistics
            agent_health: Agent health status

        Returns:
            Summary dictionary
        """
        daily_pnl = account_status.get("realized_pnl", 0)
        unrealized_pnl = account_status.get("unrealized_pnl", 0)

        return {
            "date": get_datetime_now().strftime("%Y-%m-%d"),
            "account_status": account_status,
            "positions": positions,
            "daily_pnl": daily_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": daily_pnl + unrealized_pnl,
            "workflow_stats": workflow_stats,
            "agent_health": {
                k: {
                    "is_healthy": v.get("is_healthy", False),
                    "error_count": v.get("error_count", 0),
                }
                for k, v in agent_health.items()
            },
        }
