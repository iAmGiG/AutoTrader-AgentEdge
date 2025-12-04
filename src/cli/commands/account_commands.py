"""
Account management commands for interactive CLI.

Provides natural language interface for:
- Listing accounts
- Switching active account
- Viewing account details
- Account discovery

Issue #401: Multi-Account Portfolio Management
"""

import logging
from typing import Dict, Optional

from src.trading.accounts.account_manager import get_account_manager
from src.utils.safe_print import get_symbol, safe_print

logger = logging.getLogger(__name__)


class AccountCommands:
    """
    Account management commands for CLI.

    Available commands:
    - list accounts / show accounts
    - switch to account <ID>
    - use account <ID>
    - show current account
    - refresh accounts (re-discover)
    """

    def __init__(self):
        """Initialize account commands."""
        self.manager = get_account_manager()
        logger.info("AccountCommands initialized")

    def list_accounts(self, verbose: bool = False) -> Dict:
        """
        List all configured accounts.

        Args:
            verbose: Show detailed account information

        Returns:
            Dict with status and account list
        """
        safe_print(f"{get_symbol('INFO')} Configured Trading Accounts:")
        print("=" * 60)

        accounts = self.manager.list_accounts()

        if not accounts:
            safe_print(f"{get_symbol('WARNING')} No accounts configured.")
            print("\nTo add accounts, update config/config.json with:")
            print('  "accounts": [')
            print('    {"id": "paper_main", "api_key": "...", "api_secret": "..."}')
            print("  ]")
            return {"status": "no_accounts", "accounts": []}

        for acc in accounts:
            status_icon = get_symbol("SUCCESS") if acc.get("has_info") else get_symbol("WARNING")
            active_tag = " [ACTIVE]" if acc.get("is_active") else ""
            enabled_tag = "" if acc.get("enabled", True) else " [DISABLED]"

            print(f"\n{status_icon} {acc['id']}{active_tag}{enabled_tag}")

            if acc.get("alias"):
                print(f"   Alias: {acc['alias']}")

            if acc.get("has_info"):
                acc_type = acc.get("account_type", "unknown").upper()
                print(f"   Type: {acc_type}")

                if verbose:
                    print(f"   Account #: {acc.get('account_number', 'N/A')}")
                    print(f"   Status: {acc.get('status', 'Unknown')}")

                print(f"   Portfolio: ${acc.get('portfolio_value', 0):,.2f}")
                print(f"   Buying Power: ${acc.get('buying_power', 0):,.2f}")
            else:
                error = acc.get("last_error", "Discovery pending")
                print(f"   Status: Not discovered ({error})")

        print("\n" + "=" * 60)
        print(f"Total: {len(accounts)} account(s) configured")

        active_id = self.manager.get_active_account_id()
        if active_id:
            print(f"Active: {active_id}")

        return {"status": "success", "accounts": accounts, "active": active_id}

    def switch_account(self, account_id: str) -> Dict:
        """
        Switch to a different trading account.

        Args:
            account_id: Account to switch to

        Returns:
            Dict with status and account info
        """
        safe_print(f"{get_symbol('GEAR')} Switching to account: {account_id}")

        # Try to set as active
        if self.manager.set_active_account(account_id):
            active = self.manager.get_active_account()
            if active and active.info:
                safe_print(f"{get_symbol('SUCCESS')} Now using: {account_id}")
                print(f"   Type: {active.info.account_type.value.upper()}")
                print(f"   Portfolio: ${active.info.portfolio_value:,.2f}")

                # Safety warning for live accounts
                if active.info.account_type.value == "live":
                    safe_print(
                        f"\n{get_symbol('WARNING')} *** LIVE ACCOUNT - Real money at risk! ***"
                    )

                return {
                    "status": "success",
                    "account_id": account_id,
                    "account_type": active.info.account_type.value,
                    "portfolio_value": active.info.portfolio_value,
                }

        safe_print(f"{get_symbol('ERROR')} Failed to switch to account: {account_id}")
        print("   Account may not exist or failed discovery")
        print("   Use 'list accounts' to see available accounts")
        return {"status": "error", "account_id": account_id}

    def show_current_account(self) -> Dict:
        """
        Show details of currently active account.

        Returns:
            Dict with active account info
        """
        active_id = self.manager.get_active_account_id()

        if not active_id:
            safe_print(f"{get_symbol('INFO')} No account currently active")
            print("   Use 'switch to account <ID>' to select an account")
            return {"status": "no_active_account"}

        active = self.manager.get_active_account()
        if not active or not active.info:
            safe_print(f"{get_symbol('WARNING')} Active account not fully initialized")
            return {"status": "not_initialized", "account_id": active_id}

        info = active.info
        safe_print(f"{get_symbol('SUCCESS')} Active Account: {active_id}")
        print("=" * 60)

        if info.alias:
            print(f"Alias: {info.alias}")

        print(f"Type: {info.account_type.value.upper()}")
        print(f"Account #: {info.account_number}")
        print(f"Status: {info.status}")
        print()
        print(f"Portfolio Value: ${info.portfolio_value:,.2f}")
        print(f"Cash: ${info.cash:,.2f}")
        print(f"Buying Power: ${info.buying_power:,.2f}")

        if info.pattern_day_trader:
            print(f"\n{get_symbol('WARNING')} Pattern Day Trader: Yes")

        if info.trading_blocked or info.account_blocked:
            safe_print(f"\n{get_symbol('ERROR')} Trading Blocked: Yes")

        return {
            "status": "success",
            "account_id": active_id,
            "account_info": {
                "alias": info.alias,
                "type": info.account_type.value,
                "portfolio_value": info.portfolio_value,
                "buying_power": info.buying_power,
            },
        }

    def refresh_accounts(self) -> Dict:
        """
        Re-discover all accounts (query Alpaca API for fresh data).

        Returns:
            Dict with refresh status
        """
        safe_print(f"{get_symbol('GEAR')} Refreshing account information...")

        results = self.manager.discover_all_accounts()

        success_count = sum(1 for info in results.values() if info is not None)
        total_count = len(results)

        safe_print(f"{get_symbol('SUCCESS')} Discovered {success_count}/{total_count} accounts")

        # Show any failures
        for account_id, info in results.items():
            if info is None:
                account = self.manager.get_account(account_id)
                error = account.last_error if account else "Unknown error"
                safe_print(f"{get_symbol('WARNING')} {account_id}: {error}")

        return {
            "status": "success",
            "discovered": success_count,
            "total": total_count,
            "results": results,
        }

    def get_account_for_agent(self, account_id: Optional[str] = None) -> Optional[Dict]:
        """
        Get account info for agent use (no printing).

        Args:
            account_id: Specific account or None for active

        Returns:
            Dict with account info or None
        """
        if account_id:
            account = self.manager.get_account(account_id)
        else:
            account = self.manager.get_active_account()

        if not account or not account.info:
            return None

        return {
            "account_id": account.info.account_id,
            "account_type": account.info.account_type.value,
            "portfolio_value": account.info.portfolio_value,
            "buying_power": account.info.buying_power,
            "cash": account.info.cash,
            "trading_blocked": account.info.trading_blocked,
        }


# Singleton for CLI access
_account_commands: Optional[AccountCommands] = None


def get_account_commands() -> AccountCommands:
    """Get singleton AccountCommands instance."""
    global _account_commands
    if _account_commands is None:
        _account_commands = AccountCommands()
    return _account_commands
