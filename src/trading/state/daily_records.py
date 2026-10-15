"""
Daily account records (#574 stage B).

Each scheduler routine stores the account's equity, its positions with their cost basis,
and every order filled since the last run, in state/user.db. From these, the day's P&L
(equity against the previous close) and the realized P&L of each sale (average cost, as
Alpaca reports ``avg_entry_price``) can be reviewed later.

A routine run is one account_daily row; its ``recorded_at`` is when the broker state was
fetched, and its position_daily rows are the positions at that moment (a symbol absent
from a run was not held). Timestamps are UTC ISO strings; ``market_date`` is the ET
trading day.
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional
from zoneinfo import ZoneInfo

from src.utils.state_paths import get_user_db_path

logger = logging.getLogger(__name__)

MARKET_TIMEZONE = ZoneInfo("America/New_York")  # trading days are ET dates

QTY_EPSILON = 1e-9  # fractional-share rounding


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse(timestamp: str) -> datetime:
    """An ISO timestamp as an aware datetime (naive values are UTC)."""
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _market_date(timestamp: str) -> str:
    return _parse(timestamp).astimezone(MARKET_TIMEZONE).date().isoformat()


def _day_pnl(equity: Optional[float], last_equity: Optional[float]) -> Optional[float]:
    """Equity change since the previous close; None without both values."""
    if equity is None or not last_equity:
        return None
    return equity - last_equity


def _filled_orders(orders: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Orders and bracket legs with a fill, once each, with the parent's id for a leg.

    A leg can appear both nested under its parent and at top level (get_orders() keeps
    ID-only legs it attaches); the nested copy, which knows its parent, wins.
    """
    found: Dict[str, Dict[str, Any]] = {}
    for order in orders:
        items = [(order, None)] + [(leg, order.get("id")) for leg in order.get("legs") or []]
        for item, parent_id in items:
            filled = (item.get("filled_qty") or 0) > 0
            if not (filled and item.get("filled_at") and item.get("filled_avg_price")):
                continue
            known = found.get(item["id"])
            if known is None or (parent_id and not known["parent_order_id"]):
                found[item["id"]] = {**item, "parent_order_id": parent_id}
    return list(found.values())


class DailyRecords:
    """Account, position and fill records in state/user.db."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path or get_user_db_path()
        with self._connect() as conn:
            conn.executescript("""
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
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection that commits on success and is always closed."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------ recording

    def record_account(
        self,
        market_date: str,
        routine: str,
        account: Dict[str, Any],
        recorded_at: Optional[str] = None,
    ) -> None:
        """
        Store the account at a routine run; a re-run of the routine replaces it.

        Args:
            recorded_at: When the broker state was fetched (UTC ISO; default now)
        """
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
                    recorded_at or _utc_now(),
                    account.get("equity"),
                    account.get("last_equity"),
                    account.get("cash"),
                    account.get("buying_power"),
                    account.get("portfolio_value"),
                ),
            )

    def record_positions(
        self,
        market_date: str,
        routine: str,
        positions: Dict[str, Dict[str, Any]],
        recorded_at: Optional[str] = None,
    ) -> None:
        """
        Store positions (BrokerStateCache.fetch() shape: symbol -> quantity, entry_price,
        current_price, unrealized_pl); a re-run of the routine replaces them.

        Args:
            recorded_at: When the broker state was fetched (UTC ISO; default now)
        """
        recorded_at = recorded_at or _utc_now()
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
                        recorded_at,
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
        new = []
        with self._connect() as conn:
            for fill in _filled_orders(orders):
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

    def _runs(self) -> List[sqlite3.Row]:
        """Every routine run (market_date, routine, recorded_at), oldest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT market_date, routine, recorded_at FROM account_daily"
            ).fetchall()
        return sorted(rows, key=lambda r: _parse(r["recorded_at"]))

    def last_symbols(self) -> List[str]:
        """Symbols held at the latest recorded run."""
        runs = self._runs()
        if not runs:
            return []
        latest = runs[-1]
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT symbol FROM position_daily WHERE market_date = ? AND routine = ?",
                (latest["market_date"], latest["routine"]),
            ).fetchall()
        return sorted(row["symbol"] for row in rows)

    def account_on(self, market_date: str) -> Optional[Dict[str, Any]]:
        """The day's latest account record (evening if it ran), or None."""
        runs = [r for r in self._runs() if r["market_date"] == market_date]
        if not runs:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM account_daily WHERE market_date = ? AND routine = ?",
                (market_date, runs[-1]["routine"]),
            ).fetchone()
        return dict(row)

    def equity_series(self) -> List[Dict[str, Any]]:
        """Each recorded day's latest equity and its change from the previous close."""
        series = []
        for market_date in sorted({r["market_date"] for r in self._runs()}):
            account = self.account_on(market_date)
            series.append(
                {
                    "market_date": market_date,
                    "routine": account["routine"],
                    "equity": account["equity"],
                    "last_equity": account["last_equity"],
                    "day_pnl": _day_pnl(account["equity"], account["last_equity"]),
                }
            )
        return series

    def fills_on(self, market_date: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM fills WHERE market_date = ? ORDER BY filled_at", (market_date,)
            ).fetchall()
        return [dict(row) for row in rows]

    def fills_after(self, after: Optional[str]) -> List[Dict[str, Any]]:
        """Fills after a time (UTC ISO), oldest first; all fills if None."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM fills").fetchall()
        fills = [dict(row) for row in rows]
        if after is not None:
            cutoff = _parse(after)
            fills = [f for f in fills if _parse(f["filled_at"]) > cutoff]
        return sorted(fills, key=lambda f: _parse(f["filled_at"]))

    def _cost_basis(self, symbol: str, before: str) -> Optional[float]:
        """
        Average cost of a long position just before a fill.

        Starts from the latest routine run before the fill (the symbol's recorded
        position, or flat if the run didn't hold it) and replays the fills since on the
        average-cost method. None if no run came before, or if the fills don't add up
        (a sale larger than the holding means some fills are missing).
        """
        cutoff = _parse(before)
        runs = [r for r in self._runs() if _parse(r["recorded_at"]) < cutoff]
        if not runs:
            return None
        run = runs[-1]
        since = _parse(run["recorded_at"])
        with self._connect() as conn:
            position = conn.execute(
                """
                SELECT quantity, avg_entry_price FROM position_daily
                WHERE market_date = ? AND routine = ? AND symbol = ?
                """,
                (run["market_date"], run["routine"], symbol),
            ).fetchone()
            fills = conn.execute(
                "SELECT side, filled_qty, filled_avg_price, filled_at FROM fills WHERE symbol = ?",
                (symbol,),
            ).fetchall()

        qty, cost = (position["quantity"], position["avg_entry_price"]) if position else (0.0, 0.0)
        for fill in sorted(fills, key=lambda f: _parse(f["filled_at"])):
            if not since < _parse(fill["filled_at"]) < cutoff:
                continue
            if fill["side"] == "buy":
                total = qty + fill["filled_qty"]
                cost = (qty * cost + fill["filled_qty"] * fill["filled_avg_price"]) / total
                qty = total
            else:
                qty -= fill["filled_qty"]
                if qty < -QTY_EPSILON:
                    return None
                if qty <= QTY_EPSILON:
                    qty, cost = 0.0, 0.0  # flat: the next buy starts a new basis
        return cost if qty > QTY_EPSILON else None

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

    def _previous_run_at(self, market_date: str, routine: str) -> Optional[str]:
        """When the run before this one fetched its state (any other routine run)."""
        this = [
            r for r in self._runs() if (r["market_date"], r["routine"]) == (market_date, routine)
        ]
        others = [
            r for r in self._runs() if (r["market_date"], r["routine"]) != (market_date, routine)
        ]
        if this:
            this_at = _parse(this[0]["recorded_at"])
            others = [r for r in others if _parse(r["recorded_at"]) < this_at]
        return others[-1]["recorded_at"] if others else None

    def summary_lines(self, market_date: str, routine: str) -> List[str]:
        """
        Report lines for a routine run: equity and day P&L, the fills since the previous
        run (the same on a retry of this run), and the day's realized P&L.
        """
        lines = ["", "## Daily Records", ""]
        account = self.account_on(market_date)
        if account and account["equity"] is not None:
            pnl = _day_pnl(account["equity"], account["last_equity"])
            day = f" (day P&L {pnl:+,.2f} vs the previous close)" if pnl is not None else ""
            lines.append(f"- Equity ${account['equity']:,.2f}{day}")

        previous = self._previous_run_at(market_date, routine)
        fills = self.fills_after(previous) if previous else self.fills_on(market_date)
        if fills:
            since = "the previous run" if previous else "the start of the day"
            lines.append(f"- Fills since {since}: {len(fills)}")
            for fill in fills:
                lines.append(
                    f"  - {fill['symbol']} {fill['side']} {fill['filled_qty']:g} "
                    f"@ ${fill['filled_avg_price']:,.2f} ({fill['order_type'] or '?'}, "
                    f"{fill['market_date']})"
                )
        else:
            lines.append("- No fills since the previous run")

        sales = self.realized_on(market_date)
        if sales:
            known = [s["pnl"] for s in sales if s["pnl"] is not None]
            unknown = len(sales) - len(known)
            lines.append(
                f"- Realized P&L today: {sum(known):+,.2f} over {len(known)} sale(s)"
                + (f"; {unknown} with unknown cost basis" if unknown else "")
            )
        return lines
