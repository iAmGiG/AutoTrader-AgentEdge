"""
About Page - Quick status dashboard for AgentEdge.

Displays account info, market status, and system info
in a compact, premium format.
"""

import logging
import subprocess
from datetime import datetime
from typing import Dict, Tuple
from zoneinfo import ZoneInfo

from src.utils.date_utils import (
    get_datetime_now,
    get_market_close_time,
    get_market_open_time,
    today_str,
)
from src.utils.safe_print import get_symbol, safe_print

# NYSE timezone
NYSE_TZ = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)

# AgentEdge branding
APP_NAME = "AgentEdge"
APP_TAGLINE = "Multi-Agent Trading System"


def _get_repo_url() -> str:
    """Get repository URL from git config."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Clean up git URL formats
            url = url.replace("git@github.com:", "github.com/")
            url = url.replace(".git", "")
            if url.startswith("https://"):
                url = url[8:]  # Remove https://
            return url
    except (subprocess.TimeoutExpired, OSError):
        pass
    return "github.com/AutoGen-Trader"


def _get_nyse_time() -> Tuple[str, str, str]:
    """
    Get current NYSE time and market status.

    Returns:
        Tuple of (formatted_time, market_status, next_event)
    """
    try:
        now = get_datetime_now(NYSE_TZ)

        # Format time for display
        time_str = now.strftime("%a %b %d, %I:%M %p ET")

        # Get market open/close times for today
        today = today_str()
        market_open = get_market_open_time(today)
        market_close = get_market_close_time(today)

        if market_open <= now <= market_close:
            status = "OPEN"
            # Calculate time until close
            delta = market_close - now
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes = remainder // 60
            next_event = f"Closes in {hours}h {minutes}m"
        else:
            status = "CLOSED"
            # Calculate next open
            if now > market_close:
                # After close, next open is tomorrow
                next_event = "Opens tomorrow 9:30 AM"
            else:
                # Before open today
                delta = market_open - now
                hours, remainder = divmod(int(delta.total_seconds()), 3600)
                minutes = remainder // 60
                next_event = f"Opens in {hours}h {minutes}m"

        return time_str, status, next_event

    except Exception as e:
        logger.debug(f"Error getting market time: {e}")
        return datetime.now().strftime("%a %b %d, %I:%M %p"), "UNKNOWN", ""


def _get_account_info(account_monitor) -> Dict[str, str]:
    """
    Get account information for display.

    Args:
        account_monitor: AlpacaAccountMonitor instance (optional)

    Returns:
        Dict with account info including:
        - name: Account name or "Not connected"
        - type: "Paper" or "Live" or ""
        - status: "connected", "paper", "disconnected"
        - equity, cash: Formatted amounts
    """
    info = {
        "name": "Not connected",
        "type": "",
        "status": "disconnected",
        "status_indicator": get_symbol("ERROR"),  # ❌ / [ERROR] for disconnected
        "equity": "$--",
        "cash": "$--",
    }

    if account_monitor is None:
        return info

    try:
        # Use get_account_status() which returns a dict (same as portfolio_tools)
        account = account_monitor.get_account_status()
        if account:
            # We have a connection
            info["status"] = "connected"

            # Get account name from manager if available
            try:
                from src.trading.accounts.account_manager import get_account_manager

                mgr = get_account_manager()
                active = mgr.get_active_account()
                info["name"] = active.get("name", "default") if active else "default"
            except (ImportError, AttributeError, Exception):
                info["name"] = "default"

            # Check if paper trading via account_monitor
            is_paper = getattr(account_monitor, "is_paper", True)

            # Set type and indicator based on paper/live
            if is_paper:
                info["type"] = "Paper"
                info["status"] = "paper"
                info["status_indicator"] = get_symbol("HOLD")  # 🟡 / [HOLD] for paper
            else:
                info["type"] = "Live"
                info["status"] = "live"
                info["status_indicator"] = get_symbol("SUCCESS")  # ✅ / [OK] for live

            # Format equity and cash from dict
            equity = float(account.get("equity", 0))
            cash = float(account.get("cash", 0))
            info["equity"] = f"${equity:,.2f}"
            info["cash"] = f"${cash:,.2f}"

    except Exception as e:
        logger.debug(f"Error getting account info: {e}")
        info["status"] = "error"
        info["status_indicator"] = get_symbol("ERROR")

    return info


def show_about(account_monitor=None) -> str:
    """
    Generate the about page content.

    Args:
        account_monitor: Optional AlpacaAccountMonitor for live data

    Returns:
        Formatted about page string
    """
    lines = []
    width = 50

    # Get dynamic data
    time_str, market_status, next_event = _get_nyse_time()
    account = _get_account_info(account_monitor)
    repo_url = _get_repo_url()

    # Market status indicator
    status_indicator = "*" if market_status == "OPEN" else "o"

    # Build output
    lines.append("")
    lines.append("=" * width)
    lines.append(f"{'A G E N T E D G E':^{width}}")
    lines.append("=" * width)

    # Account section with status indicator
    account_type = f" ({account['type']})" if account["type"] else ""
    lines.append(f"Account   {account['status_indicator']} {account['name']}{account_type}")
    lines.append(f"Equity    {account['equity']}")
    lines.append(f"Cash      {account['cash']}")

    lines.append("-" * width)

    # Market section
    lines.append(f"Market    {status_indicator} {market_status}")
    lines.append(f"NYSE      {time_str}")
    if next_event:
        lines.append(f"Next      {next_event}")

    lines.append("-" * width)

    # Footer
    lines.append(f"Docs      {repo_url}")

    lines.append("=" * width)
    lines.append("")

    return "\n".join(lines)


def display_about(account_monitor=None) -> None:
    """Display about page using safe_print."""
    output = show_about(account_monitor)
    safe_print(output)


__all__ = [
    "show_about",
    "display_about",
    "APP_NAME",
    "APP_TAGLINE",
]
