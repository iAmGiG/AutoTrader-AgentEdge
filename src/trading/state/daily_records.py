"""
Daily account records (#574 stage B).

Each scheduler routine stores the account's equity, its positions with their cost basis,
and every order filled since the last run, in state/user.db. From these, the day's P&L
(equity against the previous close) and the realized P&L of each sale (average cost, as
Alpaca reports ``avg_entry_price``) can be reviewed later.

Timestamps are UTC ISO strings; ``market_date`` is the ET trading day.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from src.utils.state_paths import get_user_db_path

logger = logging.getLogger(__name__)

MARKET_TIMEZONE = ZoneInfo("America/New_York")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(timestamp: str) -> datetime:
    """An ISO timestamp as an aware datetime (naive values are UTC)."""
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _market_date(timestamp: str) -> str:
    return _parse(timestamp).astimezone(MARKET_TIMEZONE).date().isoformat()


def _filled_orders(orders: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    """Orders and bracket legs with a fill, each with its parent's id (None at top level)."""
    for order in orders:
        for item, parent_id in [(order, None)] + [
            (leg, order.get("id")) for leg in order.get("legs") or []
        ]:
            if (
                (item.get("filled_qty") or 0) > 0
                and item.get("filled_at")
                and item.get("filled_avg_price")
            ):
                yield {**item, "parent_order_id": parent_id}


class DailyRecords:
    """Account, position and fill records in state/user.db."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or get_user_db_path()
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS account_daily (
                    market_date TEXT NOT NULL,
                    routine TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    equity REAL,
                    last_equity REAL,
                    cash REAL,
                    buying_power REAL,
                    portfolio_value REAL,
                    PRIMARY KEY (market_date, routine)
                );
                CREATE TABLE IF NOT EXISTS position_daily (
                    market_date TEXT NOT NULL,
                    routine TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    avg_entry_price REAL NOT NULL,
                    current_price REAL,
                    unrealized_pl REAL,
                    PRIMARY KEY (market_date, routine, symbol)
                );
                CREATE TABLE IF NOT EXISTS fills (
                    order_id TEXT PRIMARY KEY,
                    parent_order_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT,
                    order_class TEXT,
                    filled_qty REAL NOT NULL,
                    filled_avg_price REAL NOT NULL,
                    filled_at TEXT NOT NULL,
                    market_date TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_fills_symbol_time ON fills(symbol, filled_at);
            """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------ recording

    def record_account(self, market_date: str, routine: str, account: Dict[str, Any]) -> None:
        """Store the account at a routine run; a re-run of the routine replaces it."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO account_daily
                (market_date, routine, recorded_at, equity, last_equity, cash, buying_power,
                 portfolio_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    market_date,
                    routine,
                    _utc_now(),
                    account.get("equity"),
                    account.get("last_equity"),
                    account.get("cash"),
                    account.get("buying_power"),
                    account.get("portfolio_value"),
                ),
            )

    def record_positions(
        self, market_date: str, routine: str, positions: Dict[str, Dict[str, Any]]
    ) -> None:
        """
        Store positions (BrokerStateCache.fetch() shape: symbol -> quantity, entry_price,
        current_price, unrealized_pl); a re-run of the routine replaces them.
        """
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM position_daily WHERE market_date = ? AND routine = ?",
                (market_date, routine),
            )
            conn.executemany(
                """
                INSERT INTO position_daily
                (market_date, routine, symbol, recorded_at, quantity, avg_entry_price,
                 current_price, unrealized_pl)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        market_date,
                        routine,
                        symbol,
                        now,
                        position["quantity"],
                        position["entry_price"],
                        position.get("current_price"),
                        position.get("unrealized_pl"),
                    )
                    for symbol, position in positions.items()
                ],
            )

    def record_fills(self, orders: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Store filled orders and bracket legs (get_orders() shape); a later, larger partial
        fill of the same order replaces the earlier one.

        Returns:
            The fills not recorded before (or grown since), oldest first
        """
        fills = list(_filled_orders(orders))
        new = []
        with self._connect() as conn:
            for fill in fills:
                known = conn.execute(
                    "SELECT filled_qty FROM fills WHERE order_id = ?", (fill["id"],)
                ).fetchone()
                if known and known["filled_qty"] >= fill["filled_qty"]:
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO fills
                    (order_id, parent_order_id, symbol, side, order_type, order_class,
                     filled_qty, filled_avg_price, filled_at, market_date, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fill["id"],
                        fill["parent_order_id"],
                        fill["symbol"],
                        str(fill["side"]).lower(),
                        fill.get("order_type"),
                        fill.get("order_class"),
                        float(fill["filled_qty"]),
                        float(fill["filled_avg_price"]),
                        _parse(fill["filled_at"]).astimezone(timezone.utc).isoformat(),
                        _market_date(fill["filled_at"]),
                        _utc_now(),
                    ),
                )
                new.append(fill)
        return sorted(new, key=lambda f: _parse(f["filled_at"]))

    # ------------------------------------------------------------------ queries

    def account_on(self, market_date: str) -> Optional[Dict[str, Any]]:
        """The day's latest account record (evening if it ran), or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM account_daily WHERE market_date = ? ORDER BY recorded_at DESC LIMIT 1",
                (market_date,),
            ).fetchone()
        return dict(row) if row else None

    def equity_series(self) -> List[Dict[str, Any]]:
        """Each recorded day's latest equity and its change from the previous close."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.market_date, a.routine, a.equity, a.last_equity
                FROM account_daily a
                WHERE a.recorded_at = (
                    SELECT max(recorded_at) FROM account_daily b WHERE b.market_date = a.market_date
                )
                ORDER BY a.market_date
            """
            ).fetchall()
        return [
            {
                **dict(row),
                "day_pnl": (
                    row["equity"] - row["last_equity"]
                    if row["equity"] is not None and row["last_equity"] is not None
                    else None
                ),
            }
            for row in rows
        ]

    def fills_on(self, market_date: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fills WHERE market_date = ? ORDER BY filled_at", (market_date,)
            ).fetchall()
        return [dict(row) for row in rows]

    def _cost_basis(self, symbol: str, before: str) -> Optional[float]:
        """
        Average cost of a long position just before a fill: the latest recorded position,
        then the buys and sells filled since, on the average-cost method. None if unknown.
        """
        cutoff = _parse(before)
        with self._connect() as conn:
            positions = conn.execute(
                "SELECT recorded_at, quantity, avg_entry_price FROM position_daily WHERE symbol = ?",
                (symbol,),
            ).fetchall()
            fills = conn.execute(
                "SELECT side, filled_qty, filled_avg_price, filled_at FROM fills WHERE symbol = ?",
                (symbol,),
            ).fetchall()

        earlier = [p for p in positions if _parse(p["recorded_at"]) < cutoff]
        start = max(earlier, key=lambda p: _parse(p["recorded_at"]), default=None)
        since = _parse(start["recorded_at"]) if start else None
        qty = start["quantity"] if start else 0.0
        cost = start["avg_entry_price"] if start else 0.0
        for fill in sorted(fills, key=lambda f: _parse(f["filled_at"])):
            at = _parse(fill["filled_at"])
            if at >= cutoff or (since is not None and at <= since):
                continue
            if fill["side"] == "buy":
                total = qty + fill["filled_qty"]
                cost = (qty * cost + fill["filled_qty"] * fill["filled_avg_price"]) / total
                qty = total
            else:
                qty -= fill["filled_qty"]
        return cost if qty > 0 else None

    def realized_on(self, market_date: str) -> List[Dict[str, Any]]:
        """
        Realized P&L of each sale filled on a trading day (long positions, average cost).

        Returns:
            One dict per sell fill with symbol, qty, price, cost_basis and pnl (both None
            when the cost basis is unknown, e.g. a position bought before records began)
        """
        realized = []
        for fill in self.fills_on(market_date):
            if fill["side"] != "sell":
                continue
            basis = self._cost_basis(fill["symbol"], fill["filled_at"])
            realized.append(
                {
                    "symbol": fill["symbol"],
                    "qty": fill["filled_qty"],
                    "price": fill["filled_avg_price"],
                    "order_type": fill["order_type"],
                    "cost_basis": basis,
                    "pnl": (
                        (fill["filled_avg_price"] - basis) * fill["filled_qty"]
                        if basis is not None
                        else None
                    ),
                }
            )
        return realized

    def summary_lines(self, market_date: str, new_fills: List[Dict[str, Any]]) -> List[str]:
        """Report lines: equity and day P&L, new fills, and the day's realized P&L."""
        lines = ["", "## Daily Records", ""]
        account = self.account_on(market_date)
        if account and account["equity"] is not None:
            day = (
                f" (day P&L {account['equity'] - account['last_equity']:+,.2f} vs the previous close)"
                if account["last_equity"]
                else ""
            )
            lines.append(f"- Equity ${account['equity']:,.2f}{day}")
        if new_fills:
            lines.append(f"- New fills since the last run: {len(new_fills)}")
            for fill in new_fills:
                lines.append(
                    f"  - {fill['symbol']} {str(fill['side']).lower()} {fill['filled_qty']:g} "
                    f"@ ${float(fill['filled_avg_price']):,.2f} ({fill.get('order_type') or '?'}, "
                    f"{_market_date(fill['filled_at'])})"
                )
        else:
            lines.append("- No new fills since the last run")
        sales = self.realized_on(market_date)
        if sales:
            known = [s["pnl"] for s in sales if s["pnl"] is not None]
            unknown = len(sales) - len(known)
            lines.append(
                f"- Realized P&L today: {sum(known):+,.2f} over {len(known)} sale(s)"
                + (f"; {unknown} with unknown cost basis" if unknown else "")
            )
        return lines
