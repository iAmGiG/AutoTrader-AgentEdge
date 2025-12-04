"""
Account management tools for AutoGen agents.

Provides tool functions that agents can call for account operations.
Compatible with AutoGen tool registration.

Issue #401: Multi-Account Portfolio Management
"""

import logging
from typing import Any, Dict, List, Optional

from .account_manager import get_account_manager

logger = logging.getLogger(__name__)


def get_available_accounts() -> List[Dict[str, Any]]:
    """
    Get list of all available trading accounts.

    Returns:
        List of account dictionaries with status

    Example:
        >>> accounts = get_available_accounts()
        >>> for acc in accounts:
        ...     print(f"{acc['id']}: ${acc.get('portfolio_value', 0):,.2f}")
    """
    manager = get_account_manager()
    accounts = manager.list_accounts()

    return [
        {
            "id": acc["id"],
            "alias": acc.get("alias", ""),
            "type": acc.get("account_type", "unknown"),
            "enabled": acc.get("enabled", True),
            "is_active": acc.get("is_active", False),
            "has_info": acc.get("has_info", False),
            "portfolio_value": acc.get("portfolio_value", 0),
            "buying_power": acc.get("buying_power", 0),
        }
        for acc in accounts
    ]


def get_active_account_info() -> Optional[Dict[str, Any]]:
    """
    Get information about the currently active account.

    Returns:
        Dict with active account info or None if no account active

    Example:
        >>> info = get_active_account_info()
        >>> if info:
        ...     print(f"Active: {info['id']} (${info['portfolio_value']:,.2f})")
    """
    manager = get_account_manager()
    account = manager.get_active_account()

    if not account or not account.info:
        return None

    return {
        "id": account.info.account_id,
        "alias": account.info.alias,
        "type": account.info.account_type.value,
        "account_number": account.info.account_number,
        "portfolio_value": account.info.portfolio_value,
        "cash": account.info.cash,
        "buying_power": account.info.buying_power,
        "trading_blocked": account.info.trading_blocked,
        "pattern_day_trader": account.info.pattern_day_trader,
    }


def switch_active_account(account_id: str) -> Dict[str, Any]:
    """
    Switch to a different trading account.

    Args:
        account_id: ID of account to switch to

    Returns:
        Dict with result status

    Example:
        >>> result = switch_active_account("paper_main")
        >>> if result["success"]:
        ...     print(f"Switched to {result['account_id']}")
    """
    manager = get_account_manager()

    if manager.set_active_account(account_id):
        active = manager.get_active_account()
        if active and active.info:
            return {
                "success": True,
                "account_id": account_id,
                "account_type": active.info.account_type.value,
                "portfolio_value": active.info.portfolio_value,
                "message": f"Switched to account: {account_id}",
            }

    return {
        "success": False,
        "account_id": account_id,
        "message": f"Failed to switch to account: {account_id}",
    }


def refresh_account_data(account_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Refresh account data by querying Alpaca API.

    Args:
        account_id: Specific account to refresh, or None for all

    Returns:
        Dict with refresh status

    Example:
        >>> result = refresh_account_data("paper_main")
        >>> if result["success"]:
        ...     print(f"Refreshed: {result['refreshed_count']} accounts")
    """
    manager = get_account_manager()

    if account_id:
        # Refresh specific account
        info = manager.discover_account(account_id)
        return {
            "success": info is not None,
            "account_id": account_id,
            "refreshed_count": 1 if info else 0,
            "message": (
                f"Refreshed account: {account_id}" if info else f"Failed to refresh: {account_id}"
            ),
        }
    else:
        # Refresh all accounts
        results = manager.discover_all_accounts()
        success_count = sum(1 for info in results.values() if info is not None)
        return {
            "success": success_count > 0,
            "refreshed_count": success_count,
            "total_count": len(results),
            "message": f"Refreshed {success_count}/{len(results)} accounts",
        }


def get_account_buying_power(account_id: Optional[str] = None) -> Optional[float]:
    """
    Get buying power for an account.

    Args:
        account_id: Account to check, or None for active account

    Returns:
        Buying power as float, or None if account not found

    Example:
        >>> bp = get_account_buying_power()
        >>> if bp:
        ...     print(f"Available: ${bp:,.2f}")
    """
    manager = get_account_manager()

    if account_id:
        account = manager.get_account(account_id)
    else:
        account = manager.get_active_account()

    if account and account.info:
        return account.info.buying_power

    return None


def is_account_paper_trading(account_id: Optional[str] = None) -> Optional[bool]:
    """
    Check if account is paper trading (not live).

    Args:
        account_id: Account to check, or None for active account

    Returns:
        True if paper, False if live, None if unknown

    Example:
        >>> is_paper = is_account_paper_trading()
        >>> if is_paper:
        ...     print("Safe: Paper trading mode")
    """
    manager = get_account_manager()

    if account_id:
        account = manager.get_account(account_id)
    else:
        account = manager.get_active_account()

    if account and account.info:
        return account.info.account_type.value == "paper"

    return None


# Tool registration metadata for AutoGen
ACCOUNT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_available_accounts",
            "description": "List all configured trading accounts with their status and portfolio values",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_account_info",
            "description": "Get detailed information about the currently active trading account",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "switch_active_account",
            "description": "Switch to a different trading account by ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "The ID of the account to switch to (e.g., 'paper_main', 'live_trading')",
                    }
                },
                "required": ["account_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_buying_power",
            "description": "Get the available buying power for an account",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Account ID to check (optional, defaults to active account)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "is_account_paper_trading",
            "description": "Check if an account is paper trading (not live trading)",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_id": {
                        "type": "string",
                        "description": "Account ID to check (optional, defaults to active account)",
                    }
                },
                "required": [],
            },
        },
    },
]
