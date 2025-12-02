"""
Enum mapping utilities for Alpaca trading API.

Issue #437: Extract duplicated enum mapping logic from alpaca_trading_client.py
Provides reusable mappers for TimeInForce, OrderSide, and other enums.
"""

import logging
from typing import Optional

try:
    from alpaca.trading.enums import OrderSide, TimeInForce
    ALPACA_ENUMS_AVAILABLE = True
except ImportError:
    OrderSide = None
    TimeInForce = None
    ALPACA_ENUMS_AVAILABLE = False

logger = logging.getLogger(__name__)


def map_time_in_force(time_in_force: str) -> Optional:
    """
    Map string time-in-force value to Alpaca enum.

    Args:
        time_in_force: String value ("day", "gtc", "ioc", "fok")

    Returns:
        Alpaca TimeInForce enum value

    Raises:
        ValueError: If time_in_force is invalid
    """
    if not ALPACA_ENUMS_AVAILABLE:
        raise ImportError("alpaca-py SDK is required for enum mapping")

    tif_map = {
        "day": TimeInForce.DAY,
        "gtc": TimeInForce.GTC,
        "ioc": TimeInForce.IOC,
        "fok": TimeInForce.FOK,
    }

    normalized = time_in_force.lower().strip()
    if normalized not in tif_map:
        raise ValueError(
            f"Invalid time_in_force '{time_in_force}'. "
            f"Valid values: {', '.join(tif_map.keys())}"
        )

    return tif_map[normalized]


def map_side(side: str) -> Optional:
    """
    Map string side value to Alpaca enum.

    Args:
        side: String value ("buy" or "sell")

    Returns:
        Alpaca OrderSide enum value

    Raises:
        ValueError: If side is invalid
    """
    if not ALPACA_ENUMS_AVAILABLE:
        raise ImportError("alpaca-py SDK is required for enum mapping")

    normalized = side.lower().strip()
    if normalized == "buy":
        return OrderSide.BUY
    elif normalized == "sell":
        return OrderSide.SELL
    else:
        raise ValueError(f"Side must be 'buy' or 'sell', got '{side}'")


def validate_symbol(symbol: str) -> str:
    """
    Validate and normalize stock symbol.

    Args:
        symbol: Stock symbol string

    Returns:
        Normalized symbol (uppercase)

    Raises:
        ValueError: If symbol is empty or invalid
    """
    if not symbol or not symbol.strip():
        raise ValueError("Symbol is required and cannot be empty")

    normalized = symbol.strip().upper()
    if len(normalized) > 5:
        logger.warning(
            f"Symbol '{normalized}' is unusually long (>5 chars). "
            f"This may indicate an invalid symbol."
        )

    return normalized


def validate_price(price: float, name: str = "price") -> float:
    """
    Validate that price is a positive number.

    Args:
        price: Price value to validate
        name: Field name for error message (e.g., "limit_price", "stop_price")

    Returns:
        Validated price

    Raises:
        ValueError: If price is not positive
    """
    if price is None:
        raise ValueError(f"{name} cannot be None")

    if not isinstance(price, (int, float)):
        raise ValueError(f"{name} must be numeric, got {type(price).__name__}")

    if price <= 0:
        raise ValueError(f"{name} must be positive, got {price}")

    return float(price)


def validate_quantity(qty: int) -> int:
    """
    Validate that quantity is a positive integer.

    Args:
        qty: Quantity value to validate

    Returns:
        Validated quantity

    Raises:
        ValueError: If quantity is not positive
    """
    if qty is None:
        raise ValueError("Quantity cannot be None")

    if not isinstance(qty, int):
        raise ValueError(f"Quantity must be an integer, got {type(qty).__name__}")

    if qty <= 0:
        raise ValueError(f"Quantity must be positive, got {qty}")

    return int(qty)
