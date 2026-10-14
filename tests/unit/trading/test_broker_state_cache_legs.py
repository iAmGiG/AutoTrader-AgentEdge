"""BrokerStateCache keeps the working legs of filled bracket orders."""

from src.trading.state.broker_state_cache import BrokerStateCache


def _leg(oid, order_type, status, **prices):
    return {
        "id": oid,
        "symbol": "SPY",
        "side": "sell",
        "qty": 10.0,
        "status": status,
        "order_type": order_type,
        "time_in_force": "gtc",
        "limit_price": prices.get("limit_price"),
        "stop_price": prices.get("stop_price"),
        "legs": [],
    }


class FakeMonitor:
    def __init__(self, orders):
        self._orders = orders
        self.order_status_requested = None

    def get_positions(self):
        return [
            {
                "symbol": "SPY",
                "qty": "10",
                "avg_entry_price": "100",
                "market_value": "1010",
                "unrealized_pl": "10",
                "side": "long",
            }
        ]

    def get_orders(self, status="open"):
        self.order_status_requested = status
        return self._orders

    def get_account_status(self):
        return {"buying_power": 1000, "portfolio_value": 2000, "cash": 1000}


def _fetch(orders):
    monitor = FakeMonitor(orders)
    cache = BrokerStateCache(monitor, use_persistent_cache=False)
    return cache.fetch(force_refresh=True), monitor


def test_filled_bracket_parent_keeps_working_legs():
    parent = _leg("p1", "market", "filled")
    parent["side"] = "buy"
    parent["legs"] = [
        _leg("p1-tp", "limit", "new", limit_price=110.0),
        _leg("p1-sl", "stop", "held", stop_price=95.0),
    ]
    state, monitor = _fetch([parent])
    entries = {o["id"]: o for o in state["orders"]["SPY"]}
    assert set(entries) == {"p1-tp", "p1-sl"}  # filled parent itself is not a working order
    assert entries["p1-sl"]["stop_price"] == 95.0
    assert entries["p1-tp"]["limit_price"] == 110.0
    assert entries["p1-sl"]["parent_order_id"] == "p1"
    assert monitor.order_status_requested == "open"


def test_symbol_with_no_working_orders_has_no_entry():
    done = _leg("x1", "market", "filled")
    done["symbol"] = "QQQ"
    done["legs"] = [_leg("x1-tp", "limit", "filled", limit_price=1.0)]
    done["legs"][0]["symbol"] = "QQQ"
    state, _ = _fetch([done])
    assert "QQQ" not in state["orders"]


def test_orders_and_legs_keep_their_creation_time():
    # The protective-stop check (#586) needs it: Alpaca cancels GTC orders after 90 days
    parent = _leg("p1", "market", "filled")
    parent["side"] = "buy"
    stop = _leg("p1-sl", "stop", "held", stop_price=95.0)
    stop["created_at"] = "2025-09-12T08:00:00+00:00"
    standalone = _leg("s1", "stop", "new", stop_price=96.0)
    standalone["submitted_at"] = "2026-10-01T13:30:00+00:00"  # no created_at: falls back
    parent["legs"] = [stop]

    state, _ = _fetch([parent, standalone])
    entries = {o["id"]: o for o in state["orders"]["SPY"]}

    assert entries["p1-sl"]["created_at"] == "2025-09-12T08:00:00+00:00"
    assert entries["s1"]["created_at"] == "2026-10-01T13:30:00+00:00"
