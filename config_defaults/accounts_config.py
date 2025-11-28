"""
Multi-Account Configuration Schema and Defaults.

Defines the structure for multi-account trading configuration.
Used by AccountManager for loading and validating account settings.

Issue: #401 - Multi-Account Portfolio Management
Security: #402 - Credential management deferred to security issue
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AccountStrategyType(Enum):
    """Trading strategy types for account classification."""

    SET_AND_FORGET = "set_and_forget"
    ACTIVE_TRADING = "active_trading"
    RISK_MANAGEMENT = "risk_management"


@dataclass
class AccountConfigEntry:
    """
    Configuration for a single trading account.

    TODO (#402): api_key and api_secret should be retrieved from
    secure credential provider, not stored in config files.
    """

    # Required: Account identification
    id: str

    # TODO (#402): Move to secure credential provider
    # For now, credentials are loaded from config (not recommended for production)
    api_key: str = ""
    api_secret: str = ""

    # Optional: User-defined metadata
    alias: str = ""
    strategy: AccountStrategyType = AccountStrategyType.ACTIVE_TRADING
    notes: str = ""

    # Account settings
    enabled: bool = True
    is_default: bool = False

    # Risk management per account
    max_position_pct: float = 0.15  # Max 15% of portfolio per position
    max_daily_trades: int = 50
    max_portfolio_pct: float = 0.20  # Max 20% total exposure

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for config serialization."""
        return {
            "id": self.id,
            # NOTE: api_key/api_secret intentionally excluded from serialization
            # TODO (#402): Credentials should never be serialized to config
            "alias": self.alias,
            "strategy": self.strategy.value,
            "notes": self.notes,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "max_position_pct": self.max_position_pct,
            "max_daily_trades": self.max_daily_trades,
            "max_portfolio_pct": self.max_portfolio_pct,
        }


@dataclass
class AccountsConfig:
    """
    Multi-account configuration container.

    Example config.json structure:
    {
        "accounts": [
            {
                "id": "paper_main",
                "alias": "Paper Trading",
                "api_key": "PK...",      // TODO (#402): Move to keyring
                "api_secret": "...",     // TODO (#402): Move to keyring
                "strategy": "active_trading",
                "enabled": true,
                "is_default": true
            },
            {
                "id": "live_trading",
                "alias": "Live Account",
                "api_key": "AK...",
                "api_secret": "...",
                "strategy": "active_trading",
                "enabled": true
            }
        ],
        "account_settings": {
            "auto_discover": true,
            "require_confirmation_for_live": true,
            "default_account": "paper_main"
        }
    }
    """

    accounts: List[AccountConfigEntry] = field(default_factory=list)

    # Global account settings
    auto_discover: bool = True
    require_confirmation_for_live: bool = True
    default_account: Optional[str] = None

    def get_default_account(self) -> Optional[AccountConfigEntry]:
        """Get the default account entry."""
        # First try explicit default
        if self.default_account:
            for account in self.accounts:
                if account.id == self.default_account:
                    return account

        # Then try is_default flag
        for account in self.accounts:
            if account.is_default and account.enabled:
                return account

        # Finally return first enabled account
        for account in self.accounts:
            if account.enabled:
                return account

        return None

    def get_account(self, account_id: str) -> Optional[AccountConfigEntry]:
        """Get account by ID."""
        for account in self.accounts:
            if account.id == account_id:
                return account
        return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountsConfig":
        """Create AccountsConfig from dictionary (e.g., from JSON config)."""
        accounts = []
        for account_data in data.get("accounts", []):
            strategy_str = account_data.get("strategy", "active_trading")
            try:
                strategy = AccountStrategyType(strategy_str)
            except ValueError:
                strategy = AccountStrategyType.ACTIVE_TRADING

            accounts.append(
                AccountConfigEntry(
                    id=account_data.get("id", ""),
                    api_key=account_data.get("api_key", ""),
                    api_secret=account_data.get("api_secret", ""),
                    alias=account_data.get("alias", ""),
                    strategy=strategy,
                    notes=account_data.get("notes", ""),
                    enabled=account_data.get("enabled", True),
                    is_default=account_data.get("is_default", False),
                    max_position_pct=account_data.get("max_position_pct", 0.15),
                    max_daily_trades=account_data.get("max_daily_trades", 50),
                    max_portfolio_pct=account_data.get("max_portfolio_pct", 0.20),
                )
            )

        settings = data.get("account_settings", {})
        return cls(
            accounts=accounts,
            auto_discover=settings.get("auto_discover", True),
            require_confirmation_for_live=settings.get("require_confirmation_for_live", True),
            default_account=settings.get("default_account"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for config serialization."""
        return {
            "accounts": [acc.to_dict() for acc in self.accounts],
            "account_settings": {
                "auto_discover": self.auto_discover,
                "require_confirmation_for_live": self.require_confirmation_for_live,
                "default_account": self.default_account,
            },
        }


# Default configuration for new installations
DEFAULT_ACCOUNTS_CONFIG = {
    "accounts": [],  # Empty by default - user must add accounts
    "account_settings": {
        "auto_discover": True,
        "require_confirmation_for_live": True,
        "default_account": None,
    },
}


def get_example_config() -> Dict[str, Any]:
    """
    Get example multi-account configuration.

    Returns example config that users can copy and modify.
    Credentials are placeholders - actual values should come from:
    - Environment variables (for CI/CD)
    - OS Keyring (for local development) - TODO #402
    """
    return {
        "accounts": [
            {
                "id": "paper_main",
                "alias": "Paper Trading Account",
                # TODO (#402): These should be retrieved from secure storage
                "api_key": "YOUR_PAPER_API_KEY",
                "api_secret": "YOUR_PAPER_SECRET",
                "strategy": "active_trading",
                "notes": "Main paper trading for strategy testing",
                "enabled": True,
                "is_default": True,
                "max_position_pct": 0.15,
                "max_daily_trades": 50,
            },
            {
                "id": "paper_experiments",
                "alias": "Experimental Strategies",
                "api_key": "YOUR_PAPER_API_KEY_2",
                "api_secret": "YOUR_PAPER_SECRET_2",
                "strategy": "active_trading",
                "notes": "Testing new strategies before production",
                "enabled": True,
                "is_default": False,
                "max_position_pct": 0.10,
                "max_daily_trades": 20,
            },
            {
                "id": "live_conservative",
                "alias": "Live - Set and Forget",
                "api_key": "YOUR_LIVE_API_KEY",
                "api_secret": "YOUR_LIVE_SECRET",
                "strategy": "set_and_forget",
                "notes": "Long-term holdings, minimal trading",
                "enabled": False,  # Disabled by default for safety
                "is_default": False,
                "max_position_pct": 0.25,
                "max_daily_trades": 5,
            },
        ],
        "account_settings": {
            "auto_discover": True,
            "require_confirmation_for_live": True,
            "default_account": "paper_main",
        },
    }
