"""
Market Hours Validation - Facade for src.utils.market_hours.

This module is maintained for backward compatibility.
The implementation has been consolidated into src.utils.market_hours.
"""

from src.utils.market_hours import (
    validate_market_hours,
)

# Aliases for backward compatibility
check_market_hours = validate_market_hours
