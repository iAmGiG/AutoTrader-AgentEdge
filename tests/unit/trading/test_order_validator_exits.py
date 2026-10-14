"""
Selling shares already held only reduces risk, so the limits on new risk (shares per
order, order value, orders per day) must not block exits or protective stops.
"""

import pytest

from src.trading.broker.validators.order_validator import OrderValidator

LIMITS = {"max_order_size": 1000, "max_order_value": 50000, "max_daily_trades": 5}


def _validator(held_qty=None, orders_today=0):
    positions = [] if held_qty is None else [{"symbol": "SOXL", "qty": float(held_qty)}]
    return OrderValidator(
        risk_limits=LIMITS,
        account_provider=lambda: {"buying_power": 1_000_000.0},
        position_provider=lambda: positions,
        order_provider=lambda after=None: [object()] * orders_today,
    )


def test_protective_stop_above_value_cap_passes():
    # 900 x $66.50 = $59,850, over the $50k cap
    assert _validator(held_qty=900).validate_order("SOXL", 900, "sell", 66.50)


def test_exit_above_share_cap_passes():
    assert _validator(held_qty=1200).validate_order("SOXL", 1200, "sell", 30.0)


def test_exit_after_daily_trade_limit_passes():
    assert _validator(held_qty=100, orders_today=5).validate_order("SOXL", 100, "sell")


def test_buy_above_value_cap_is_still_rejected():
    with pytest.raises(ValueError, match="exceeds limit"):
        _validator(held_qty=900).validate_order("SOXL", 900, "buy", 66.50)


def test_sell_beyond_held_shares_is_still_rejected():
    with pytest.raises(ValueError, match="only 100"):
        _validator(held_qty=100).validate_order("SOXL", 200, "sell", 30.0)


def test_sell_with_unknown_position_keeps_the_caps():
    validator = OrderValidator(risk_limits=LIMITS)  # no position provider

    with pytest.raises(ValueError, match="exceeds limit"):
        validator.validate_order("SOXL", 900, "sell", 66.50)
