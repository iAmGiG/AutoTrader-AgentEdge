"""
Alert Display Tools - FunctionTool wrappers for position alerts.

Issue #433/#458: Extract alert display commands from cli_session.py.

These tools handle:
- Checking current position alerts
- Viewing alert history
- Getting alert severity and details

Note: Alerts come from the same check the routines run (StateReconciler and
PositionTracker): open positions near or through their stop, or their target where one
exists (#599).
"""

import dataclasses
import logging
from typing import Any, Dict, List

from agent_framework import FunctionTool

from src.trading.positions.position_tracker import position_key
from src.utils.safe_print import get_symbol

logger = logging.getLogger(__name__)

# Readable names for the alert types
ALERT_LABELS = {
    "approaching_sl": "near stop",
    "loss_threshold_reached": "stop breached, position still open",
    "approaching_tp": "near target",
    "profit_target_reached": "target reached, position still open",
    "stop_adjusted": "stop adjusted",
}


# =============================================================================
# Helper Functions
# =============================================================================


def _get_trading_cycle():
    """
    Get CostEfficientTradeCycle instance.

    Returns singleton or creates new instance.
    """
    try:
        from src.trading.scheduling.trading_cycle import CostEfficientTradeCycle

        return CostEfficientTradeCycle()
    except Exception as e:
        logger.error(f"Failed to get trading cycle: {e}")
        return None


def _format_alert(alert: Any) -> Dict[str, Any]:
    """
    Format a PositionAlert object to dict.

    Args:
        alert: PositionAlert or PositionAlertSummary object, or dict

    Returns:
        Formatted alert dict
    """
    if hasattr(alert, "to_dict"):
        return alert.to_dict()
    elif dataclasses.is_dataclass(alert):  # PositionAlertSummary
        formatted = dataclasses.asdict(alert)
        formatted["ticker"] = formatted.pop("symbol")
        return formatted
    elif isinstance(alert, dict):
        return alert
    else:
        # Try to extract common attributes
        return {
            "ticker": getattr(alert, "ticker", "unknown"),
            "alert_type": str(getattr(alert, "alert_type", "unknown")),
            "current_price": getattr(alert, "current_price", 0),
            "severity": getattr(alert, "severity", "INFO"),
            "details": getattr(alert, "details", {}),
            "timestamp": str(getattr(alert, "timestamp", "")),
        }


# =============================================================================
# FunctionTool Wrapper Functions
# =============================================================================


def check_alerts() -> Dict[str, Any]:
    """
    Check current position alerts.

    Fetches current broker state, reconciles it in memory (nothing is saved) and runs
    the routines' alert check: open positions near or through their stop, or their
    target where one exists.

    Returns:
        Dict with:
        - status: "success", "no_alerts", or "error"
        - alerts: List of current alert dicts
        - alert_count: Number of alerts
        - positions_monitored: Number of positions being tracked
    """
    try:
        trading_cycle = _get_trading_cycle()
        if not trading_cycle:
            return {"status": "not_initialized", "message": "Trading cycle not available"}

        if getattr(trading_cycle, "position_tracker", None) is None:
            return {"status": "not_initialized", "message": "Position tracker not available"}

        # Without the broker's positions and stops there is nothing to check against
        try:
            broker_state = trading_cycle.fetch_broker_state()
        except Exception as e:
            logger.warning(f"Failed to fetch broker state: {e}")
            return {"status": "error", "error": f"Could not reach the broker: {e}"}

        # The local levels follow the broker's live stops after a reconcile. This cycle is
        # the tool's own (_get_trading_cycle builds one per call) and is never saved, so
        # the reconcile and the tracker sync are discarded with it.
        trading_cycle.reconcile_state(broker_state)
        alerts = trading_cycle.check_position_alerts(broker_state)
        position_tracker = trading_cycle.position_tracker

        if not alerts:
            return {
                "status": "no_alerts",
                "alerts": [],
                "alert_count": 0,
                "positions_monitored": len(position_tracker.positions),
                "message": "No active alerts",
            }

        # Format alerts
        formatted_alerts = [_format_alert(a) for a in alerts]

        # Group by severity
        by_severity: Dict[str, List] = {"CRITICAL": [], "WARNING": [], "INFO": []}
        for alert in formatted_alerts:
            severity = alert.get("severity", "INFO")
            if severity in by_severity:
                by_severity[severity].append(alert)

        return {
            "status": "success",
            "alerts": formatted_alerts,
            "alert_count": len(alerts),
            "positions_monitored": len(position_tracker.positions),
            "by_severity": {k: len(v) for k, v in by_severity.items() if v},
        }

    except Exception as e:
        logger.error(f"Error checking alerts: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def get_alert_history(limit: int = 10) -> Dict[str, Any]:
    """
    Get recent alert history.

    Args:
        limit: Maximum alerts to return (default 10)

    Returns:
        Dict with:
        - status: "success" or "error"
        - history: List of historical alert dicts
        - total_alerts: Total alerts in history
    """
    try:
        trading_cycle = _get_trading_cycle()
        if not trading_cycle:
            return {"status": "not_initialized", "message": "Trading cycle not available"}

        if not hasattr(trading_cycle, "position_tracker"):
            return {"status": "not_initialized", "message": "Position tracker not available"}

        position_tracker = trading_cycle.position_tracker
        total = len(position_tracker.get_all_alerts())
        history = position_tracker.get_alert_history(limit=limit)

        if not history:
            return {
                "status": "success",
                "history": [],
                "total_alerts": 0,
                "message": "No alert history",
            }

        formatted = [_format_alert(a) for a in history]

        return {
            "status": "success",
            "history": formatted,
            "total_alerts": total,
            "returned": len(formatted),
        }

    except Exception as e:
        logger.error(f"Error getting alert history: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def get_position_alert_status(ticker: str) -> Dict[str, Any]:
    """
    Get alert status for a specific position.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with:
        - status: "success", "not_found", or "error"
        - ticker: The requested ticker
        - position_status: Current position status
        - recent_alerts: Recent alerts for this position
        - current_levels: Stop/target levels if available
    """
    try:
        trading_cycle = _get_trading_cycle()
        if not trading_cycle:
            return {"status": "not_initialized", "message": "Trading cycle not available"}

        if not hasattr(trading_cycle, "position_tracker"):
            return {"status": "not_initialized", "message": "Position tracker not available"}

        ticker_upper = ticker.upper()
        position_tracker = trading_cycle.position_tracker

        # One entry per open position, keyed by its symbol
        position_id = position_key(ticker_upper)
        position = position_tracker.positions.get(position_id)
        if position is None:
            return {
                "status": "not_found",
                "ticker": ticker_upper,
                "message": f"No tracked position for {ticker_upper}",
            }

        # Get alerts for this position
        position_alerts = [
            _format_alert(a) for a in position.alert_history if hasattr(position, "alert_history")
        ]

        return {
            "status": "success",
            "ticker": ticker_upper,
            "position_id": position_id,
            "position_status": position.status,
            "entry_price": position.entry_price,
            "quantity": position.quantity,
            "stop_loss_price": position.stop_loss_price,
            "take_profit_price": position.take_profit_price,
            "recent_alerts": position_alerts[-5:],  # Last 5 alerts
            "total_alerts": len(position_alerts),
        }

    except Exception as e:
        logger.error(f"Error getting alert status for {ticker}: {e}", exc_info=True)
        return {"status": "error", "ticker": ticker, "error": str(e)}


def get_monitored_positions_count() -> Dict[str, Any]:
    """
    Get count of positions being monitored for alerts.

    Returns:
        Dict with:
        - status: "success" or "error"
        - active_positions: Number of active positions
        - total_tracked: Total positions in tracker (including closed)
    """
    try:
        trading_cycle = _get_trading_cycle()
        if not trading_cycle:
            return {"status": "not_initialized", "message": "Trading cycle not available"}

        if not hasattr(trading_cycle, "position_tracker"):
            return {"status": "not_initialized", "message": "Position tracker not available"}

        position_tracker = trading_cycle.position_tracker
        all_positions = position_tracker.positions

        active = sum(1 for p in all_positions.values() if p.status == "ACTIVE")
        closed = sum(1 for p in all_positions.values() if p.status != "ACTIVE")

        return {
            "status": "success",
            "active_positions": active,
            "closed_positions": closed,
            "total_tracked": len(all_positions),
        }

    except Exception as e:
        logger.error(f"Error getting monitored positions count: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# =============================================================================
# Display Functions (Issue #459)
# =============================================================================


def show_alerts() -> str:
    """Display current position alerts with formatted output."""
    result = check_alerts()
    if result["status"] == "not_initialized":
        return f"{get_symbol('ERROR')} Alert system not initialized"
    if result["status"] == "error":
        return f"{get_symbol('ERROR')} Error: {result.get('error', 'Unknown')}"
    if result["status"] == "no_alerts":
        return f"{get_symbol('SUCCESS')} No active alerts\n{get_symbol('INFO')} Monitoring {result.get('positions_monitored', 0)} position(s)"

    lines = [f"{get_symbol('BELL')} Position Alerts ({result['alert_count']})", ""]
    for alert in result.get("alerts", []):
        severity = alert.get("severity", "INFO")
        emoji = (
            get_symbol("RED")
            if severity == "CRITICAL"
            else get_symbol("YELLOW")
            if severity == "WARNING"
            else get_symbol("INFO")
        )
        alert_type = alert.get("alert_type", "unknown")
        lines.append(
            f"{emoji} {alert.get('ticker', '?')}: {ALERT_LABELS.get(alert_type, alert_type)} @ ${alert.get('current_price', 0):.2f}"
        )
        details = alert.get("details", {})
        level = details.get("stop_price") or details.get("target_price")
        if level:
            distance = details.get("distance_pct", 0)
            where = f"{distance:.2f}% away" if distance >= 0 else f"{-distance:.2f}% through it"
            lines.append(f"   • level ${level:.2f}, {where}")
        if details.get("live_stop") is False:
            lines.append("   • no live stop order")

    history_result = get_alert_history(limit=5)
    if history_result.get("history"):
        lines.extend(["", f"📜 Recent History ({len(history_result['history'])})"])
        for hist in history_result["history"]:
            alert_type = hist.get("alert_type")
            lines.append(f"   {hist.get('ticker')}: {ALERT_LABELS.get(alert_type, alert_type)}")
    return "\n".join(lines)


# =============================================================================
# FunctionTool Registration
# =============================================================================


show_alerts_tool = FunctionTool(
    func=show_alerts,
    name="show_alerts",
    description="Display current position alerts with formatted output.",
)

check_alerts_tool = FunctionTool(
    func=check_alerts,
    name="check_alerts",
    description="Check current position alerts including approaching stop/target and profit zones.",
)

get_alert_history_tool = FunctionTool(
    func=get_alert_history,
    name="get_alert_history",
    description="Get recent alert history with timestamps and details.",
)

get_position_alert_status_tool = FunctionTool(
    func=get_position_alert_status,
    name="get_position_alert_status",
    description="Get alert status and stop/target levels for a specific ticker.",
)

get_monitored_positions_count_tool = FunctionTool(
    func=get_monitored_positions_count,
    name="get_monitored_positions_count",
    description="Get count of positions being monitored for alerts.",
)


# Export list for CLI tools registry
CLI_ALERT_TOOLS = [
    show_alerts_tool,
    check_alerts_tool,
    get_alert_history_tool,
    get_position_alert_status_tool,
    get_monitored_positions_count_tool,
]

__all__ = [
    # Display Functions
    "show_alerts",
    # Data Functions
    "check_alerts",
    "get_alert_history",
    "get_position_alert_status",
    "get_monitored_positions_count",
    # FunctionTools
    "CLI_ALERT_TOOLS",
    "check_alerts_tool",
    "get_alert_history_tool",
    "get_position_alert_status_tool",
    "get_monitored_positions_count_tool",
]
