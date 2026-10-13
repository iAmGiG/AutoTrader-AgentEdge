"""
Multi-Account Manager for Trading Platform.

Provides unified management of multiple trading accounts with:
- API-first discovery (Alpaca tells us account details)
- Automatic paper vs live detection
- Account context for trading operations
- Future security integration points (#402)

Issue: #401 - Multi-Account Portfolio Management
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from alpaca.trading.client import TradingClient

from src.utils.config_loader import ConfigLoader
from src.utils.date_utils import get_datetime_now

logger = logging.getLogger(__name__)

DEFAULT_MAX_POSITION_PCT = 0.15
DEFAULT_MAX_DAILY_TRADES = 50


class AccountType(Enum):
    """Account type classification."""

    PAPER = "paper"
    LIVE = "live"
    UNKNOWN = "unknown"


class AccountStrategy(Enum):
    """Account strategy classification from #401."""

    SET_AND_FORGET = "set_and_forget"  # Long-term buy-and-hold
    ACTIVE_TRADING = "active_trading"  # Regular trading with human oversight
    RISK_MANAGEMENT = "risk_management"  # Hedging, volatility plays (future)


@dataclass
class AccountCredentials:
    """
    Account credentials container.

    TODO (#402): Replace with secure credential provider interface.
    Current implementation stores credentials in memory only.
    Future: OS Keyring integration for secure storage.
    """

    api_key: str
    api_secret: str
    # TODO (#402): Add credential_provider field for secure retrieval
    # credential_provider: Optional[CredentialProvider] = None

    def __post_init__(self):
        """Validate credentials are not empty."""
        if not self.api_key or not self.api_secret:
            raise ValueError("API key and secret are required")

    def __repr__(self) -> str:
        """Safe representation - never expose secrets."""
        return f"AccountCredentials(api_key='{self.api_key[:4]}...', api_secret='***')"


@dataclass
class AccountInfo:
    """
    Discovered account information from Alpaca API.

    Populated via API-first discovery - we ask Alpaca what the account is.
    """

    account_id: str
    account_number: str
    account_type: AccountType
    status: str
    buying_power: float
    cash: float
    portfolio_value: float
    pattern_day_trader: bool
    trading_blocked: bool
    account_blocked: bool
    # User-defined metadata
    alias: str = ""
    strategy: AccountStrategy = AccountStrategy.ACTIVE_TRADING
    notes: str = ""
    # Discovery metadata
    api_endpoint: str = ""
    discovered_at: str = ""


@dataclass
class ManagedAccount:
    """
    A fully managed trading account with credentials and discovered info.

    TODO (#402): Credentials should be retrieved via secure provider, not stored.
    """

    credentials: AccountCredentials
    info: Optional[AccountInfo] = None
    is_active: bool = False
    last_error: Optional[str] = None
    # User-defined settings
    enabled: bool = True
    max_position_pct: float = DEFAULT_MAX_POSITION_PCT
    max_daily_trades: int = DEFAULT_MAX_DAILY_TRADES
    # Cache for trading client to avoid recreation
    _client: Optional[Any] = field(default=None, init=False, repr=False)


class AccountManager:
    """
    Multi-account manager with API-first discovery.

    Features:
    - Load multiple account credentials from config
    - Discover account details from Alpaca API
    - Automatic paper vs live detection
    - Account selection for trading operations
    - Future security integration points (#402)

    Usage:
        manager = AccountManager()
        manager.discover_all_accounts()
        manager.set_active_account("my_paper_account")
        account = manager.get_active_account()
    """

    def __init__(self, config_loader: Optional[ConfigLoader] = None):
        """
        Initialize account manager.

        Args:
            config_loader: Optional config loader (creates default if None)
        """
        self.config = config_loader or ConfigLoader()
        self._accounts: Dict[str, ManagedAccount] = {}
        self._active_account_id: Optional[str] = None

        # TODO (#402): Initialize credential provider
        # self._credential_provider = get_credential_provider()

        logger.info("AccountManager initialized")

    def load_accounts_from_config(self) -> int:
        """
        Load account credentials from configuration.

        Supports multiple credential formats:
        1. Legacy single account: ALPACA_PAPER_API_KEY, ALPACA_PAPER_SECRET
        2. Multi-account: accounts[] array in config

        TODO (#402): Load credentials from secure provider instead of config.

        Returns:
            Number of accounts loaded
        """
        accounts_loaded = 0

        # Try multi-account format first
        accounts_config = self.config.get("accounts", [])

        # Get global defaults from config or constants
        default_max_pos = self.config.get(
            "account.default_max_position_pct", DEFAULT_MAX_POSITION_PCT
        )
        default_max_trades = self.config.get(
            "account.default_max_daily_trades", DEFAULT_MAX_DAILY_TRADES
        )

        if accounts_config and isinstance(accounts_config, list):
            for account_cfg in accounts_config:
                try:
                    account_id = account_cfg.get("id", f"account_{accounts_loaded}")
                    # TODO (#402): Retrieve credentials from secure provider
                    # credentials = self._credential_provider.get_credentials(account_id)
                    credentials = AccountCredentials(
                        api_key=account_cfg.get("api_key", ""),
                        api_secret=account_cfg.get("api_secret", ""),
                    )

                    managed = ManagedAccount(
                        credentials=credentials,
                        enabled=account_cfg.get("enabled", True),
                        max_position_pct=account_cfg.get("max_position_pct", default_max_pos),
                        max_daily_trades=account_cfg.get("max_daily_trades", default_max_trades),
                    )

                    # Store user-defined alias if provided
                    if "alias" in account_cfg:
                        if managed.info is None:
                            managed.info = AccountInfo(
                                account_id=account_id,
                                account_number="",
                                account_type=AccountType.UNKNOWN,
                                status="pending_discovery",
                                buying_power=0,
                                cash=0,
                                portfolio_value=0,
                                pattern_day_trader=False,
                                trading_blocked=False,
                                account_blocked=False,
                                alias=account_cfg.get("alias", ""),
                            )

                    self._accounts[account_id] = managed
                    accounts_loaded += 1
                    logger.info(f"Loaded account config: {account_id}")

                except ValueError as e:
                    logger.warning(f"Skipping invalid account config: {e}")

        # Fallback to legacy single-account format
        if accounts_loaded == 0:
            # Try paper account
            paper_key = self.config.get("ALPACA_PAPER_API_KEY")
            paper_secret = self.config.get("ALPACA_PAPER_SECRET")
            if paper_key and paper_secret:
                try:
                    credentials = AccountCredentials(api_key=paper_key, api_secret=paper_secret)
                    self._accounts["paper"] = ManagedAccount(credentials=credentials)
                    accounts_loaded += 1
                    logger.info("Loaded legacy paper account credentials")
                except ValueError:
                    pass

            # Try live account
            live_key = self.config.get("ALPACA_LIVE_API_KEY")
            live_secret = self.config.get("ALPACA_LIVE_SECRET")
            if live_key and live_secret:
                try:
                    credentials = AccountCredentials(api_key=live_key, api_secret=live_secret)
                    self._accounts["live"] = ManagedAccount(credentials=credentials)
                    accounts_loaded += 1
                    logger.info("Loaded legacy live account credentials")
                except ValueError:
                    pass

        logger.info(f"Loaded {accounts_loaded} account(s) from config")
        return accounts_loaded

    def discover_account(self, account_id: str) -> Optional[AccountInfo]:
        """
        Discover account details from Alpaca API.

        Uses API-first approach: we ask Alpaca what this account is,
        rather than relying on user configuration.

        Args:
            account_id: Internal account identifier

        Returns:
            Discovered AccountInfo or None if discovery failed
        """
        if account_id not in self._accounts:
            logger.error(f"Account {account_id} not found in manager")
            return None

        managed = self._accounts[account_id]

        try:
            # Try paper endpoint first, then live
            # Alpaca paper uses paper=True, live uses paper=False
            for is_paper in [True, False]:
                try:
                    client = TradingClient(
                        api_key=managed.credentials.api_key,
                        secret_key=managed.credentials.api_secret,
                        paper=is_paper,
                    )

                    account = client.get_account()

                    # Determine account type from API response
                    # Paper accounts connect to paper-api.alpaca.markets
                    # Live accounts have status="ACTIVE" typically
                    account_type = AccountType.PAPER if is_paper else AccountType.LIVE

                    # Build discovered info
                    info = AccountInfo(
                        account_id=account_id,
                        account_number=str(account.account_number),
                        account_type=account_type,
                        status=str(account.status),
                        buying_power=float(account.buying_power or 0),
                        cash=float(account.cash or 0),
                        portfolio_value=float(account.portfolio_value or 0),
                        pattern_day_trader=bool(account.pattern_day_trader),
                        trading_blocked=bool(account.trading_blocked),
                        account_blocked=bool(account.account_blocked),
                        alias=managed.info.alias if managed.info else "",
                        api_endpoint="paper" if is_paper else "live",
                        discovered_at=get_datetime_now().isoformat(),
                    )

                    managed.info = info
                    managed.last_error = None
                    managed._client = None  # Invalidate cache on new discovery
                    logger.info(
                        f"Discovered {account_type.value} account: "
                        f"{account.account_number} (${info.portfolio_value:,.2f})"
                    )
                    return info

                except Exception as e:
                    # If paper fails, try live (and vice versa)
                    error_str = str(e).lower()
                    if "forbidden" in error_str or "unauthorized" in error_str:
                        continue
                    # Other errors should be logged
                    logger.debug(f"Discovery attempt failed (paper={is_paper}): {e}")
                    continue

            # Both endpoints failed
            managed.last_error = "Could not connect to Alpaca API"
            logger.error(f"Failed to discover account {account_id}")
            return None

        except ImportError:
            managed.last_error = "alpaca-py not installed"
            logger.error("alpaca-py SDK required for account discovery")
            return None
        except Exception as e:
            managed.last_error = str(e)
            logger.error(f"Account discovery failed for {account_id}: {e}")
            return None

    def discover_all_accounts(self) -> Dict[str, Optional[AccountInfo]]:
        """
        Discover details for all configured accounts.

        Returns:
            Dict mapping account_id to discovered AccountInfo (or None if failed)
        """
        results = {}
        for account_id in self._accounts:
            results[account_id] = self.discover_account(account_id)
        return results

    def set_active_account(self, account_id: str) -> bool:
        """
        Set the active account for trading operations.

        Args:
            account_id: Account to activate

        Returns:
            True if account was activated successfully
        """
        if account_id not in self._accounts:
            logger.error(f"Account {account_id} not found")
            return False

        managed = self._accounts[account_id]

        if not managed.enabled:
            logger.error(f"Account {account_id} is disabled")
            return False

        if managed.info is None:
            logger.warning(f"Account {account_id} not yet discovered, discovering now...")
            if not self.discover_account(account_id):
                return False

        # Deactivate previous account
        if self._active_account_id and self._active_account_id in self._accounts:
            self._accounts[self._active_account_id].is_active = False

        # Activate new account
        managed.is_active = True
        self._active_account_id = account_id

        account_type = managed.info.account_type.value if managed.info else "unknown"
        logger.info(f"Active account set to: {account_id} ({account_type})")

        # Safety warning for live accounts
        if managed.info and managed.info.account_type == AccountType.LIVE:
            logger.warning("*** LIVE ACCOUNT ACTIVATED - Real money at risk! ***")

        return True

    def rotate_active_account(self) -> Optional[str]:
        """
        Rotate to the next enabled account.
        Useful for periodic swapping or load balancing.

        Returns:
            New active account ID, or None if no accounts available.
        """
        candidates = [
            aid for aid, acc in self._accounts.items() if acc.enabled and acc.info is not None
        ]

        if not candidates:
            return None

        current = self._active_account_id
        if current in candidates:
            idx = candidates.index(current)
            next_id = candidates[(idx + 1) % len(candidates)]
        else:
            next_id = candidates[0]

        return next_id if self.set_active_account(next_id) else None

    def get_active_account(self) -> Optional[ManagedAccount]:
        """
        Get the currently active account.

        Returns:
            Active ManagedAccount or None if no account active
        """
        if self._active_account_id and self._active_account_id in self._accounts:
            return self._accounts[self._active_account_id]
        return None

    def get_active_account_id(self) -> Optional[str]:
        """Get the ID of the currently active account."""
        return self._active_account_id

    def get_account(self, account_id: str) -> Optional[ManagedAccount]:
        """
        Get a specific account by ID.

        Args:
            account_id: Account identifier

        Returns:
            ManagedAccount or None if not found
        """
        return self._accounts.get(account_id)

    def list_accounts(self) -> List[Dict[str, Any]]:
        """
        List all configured accounts with their status.

        Returns:
            List of account summary dictionaries
        """
        accounts = []
        for account_id, managed in self._accounts.items():
            summary = {
                "id": account_id,
                "enabled": managed.enabled,
                "is_active": managed.is_active,
                "has_info": managed.info is not None,
                "last_error": managed.last_error,
            }

            if managed.info:
                summary.update(
                    {
                        "alias": managed.info.alias,
                        "account_type": managed.info.account_type.value,
                        "account_number": managed.info.account_number,
                        "status": managed.info.status,
                        "portfolio_value": managed.info.portfolio_value,
                        "buying_power": managed.info.buying_power,
                    }
                )

            accounts.append(summary)

        return accounts

    def get_trading_client(self, account_id: Optional[str] = None) -> Optional[Any]:
        """
        Get Alpaca TradingClient for an account.

        Args:
            account_id: Account to get client for (uses active if None)

        Returns:
            Configured TradingClient or None
        """
        target_id = account_id or self._active_account_id
        if not target_id or target_id not in self._accounts:
            logger.error("No account specified and no active account set")
            return None

        managed = self._accounts[target_id]
        if managed.info is None:
            logger.error(f"Account {target_id} not discovered")
            return None

        # Return cached client if available
        if managed._client is not None:
            return managed._client

        try:
            is_paper = managed.info.account_type == AccountType.PAPER
            managed._client = TradingClient(
                api_key=managed.credentials.api_key,
                secret_key=managed.credentials.api_secret,
                paper=is_paper,
            )
            return managed._client
        except ImportError:
            logger.error("alpaca-py SDK required")
            return None

    def add_account(
        self,
        account_id: str,
        api_key: str,
        api_secret: str,
        alias: str = "",
        enabled: bool = True,
    ) -> bool:
        """
        Add a new account to the manager.

        TODO (#402): Store credentials in secure provider, not config.

        Args:
            account_id: Unique identifier for this account
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            alias: Human-friendly name
            enabled: Whether account is enabled for trading

        Returns:
            True if account was added successfully
        """
        if account_id in self._accounts:
            logger.error(f"Account {account_id} already exists")
            return False

        try:
            # TODO (#402): Store credentials securely
            # self._credential_provider.store_credentials(account_id, credentials)
            credentials = AccountCredentials(api_key=api_key, api_secret=api_secret)

            managed = ManagedAccount(credentials=credentials, enabled=enabled)

            # Create placeholder info with alias
            managed.info = AccountInfo(
                account_id=account_id,
                account_number="",
                account_type=AccountType.UNKNOWN,
                status="pending_discovery",
                buying_power=0,
                cash=0,
                portfolio_value=0,
                pattern_day_trader=False,
                trading_blocked=False,
                account_blocked=False,
                alias=alias,
            )

            self._accounts[account_id] = managed
            logger.info(f"Added account: {account_id}")
            return True

        except ValueError as e:
            logger.error(f"Failed to add account: {e}")
            return False

    def remove_account(self, account_id: str) -> bool:
        """
        Remove an account from the manager.

        Args:
            account_id: Account to remove

        Returns:
            True if account was removed
        """
        if account_id not in self._accounts:
            logger.error(f"Account {account_id} not found")
            return False

        if self._active_account_id == account_id:
            self._active_account_id = None

        del self._accounts[account_id]
        logger.info(f"Removed account: {account_id}")

        # TODO (#402): Remove credentials from secure provider
        # self._credential_provider.remove_credentials(account_id)

        return True


# Module-level singleton
_account_manager: Optional[AccountManager] = None


def get_account_manager() -> AccountManager:
    """
    Get the global AccountManager instance.

    Returns:
        Singleton AccountManager instance
    """
    global _account_manager
    if _account_manager is None:
        _account_manager = AccountManager()
        _account_manager.load_accounts_from_config()
    return _account_manager


def reset_account_manager() -> None:
    """Reset the global AccountManager (useful for testing)."""
    global _account_manager
    _account_manager = None
