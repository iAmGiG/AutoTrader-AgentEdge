"""
Split adjustment for equity_prices_daily.

The table stores raw prices: ``adjusted_close`` equals ``close`` and ``daily_return`` is
raw, so a split shows up as a one-day move of the split ratio (AAPL 2020-08-31 -74%,
XLK and XLE 2025-12-05 -50%). ``gex.corporate_events`` lists the splits:
``event_date`` is the first trading day at the new price (checked against the price
jump for 131 of the 133 splits inside the price history; the other two are reverse
splits on days the stock also moved a lot) and ``split_factor`` is new shares per old
share (4.0 for a 4-for-1 split, 0.1 for a 1-for-10 reverse split).

Prices are back-adjusted to the scale at a fixed anchor date (the research data's last
validated date), so a given date has the same price in every call, whichever window is
requested: every price before a split is divided by its factor and volume multiplied
by it, so returns and dollar volume are continuous. Splits after the anchor are not
applied.
"""

import logging
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

PRICE_COLUMNS = ("open", "high", "low", "close")
# A split day that still moves more than this after adjustment is logged: the stock may
# really have moved (RIOT 2012-06-20, AMC 2023-08-24), or the event date or factor is off
SUSPECT_SPLIT_DAY_MOVE = 0.25


def load_splits(conn, symbols: Iterable[str], start_date: str, anchor_date: str) -> pd.DataFrame:
    """
    Splits that affect prices in a window (columns: symbol, event_date, split_factor).

    Only splits after ``start_date`` change any price in the window (earlier ones apply
    to dates before it), and only those up to ``anchor_date`` are applied.
    """
    symbols = list(symbols)
    if not symbols:
        return pd.DataFrame(columns=["symbol", "event_date", "split_factor"])
    placeholders = ",".join(["%s"] * len(symbols))
    query = f"""
        SELECT symbol, event_date, split_factor
        FROM gex.corporate_events
        WHERE event_type = 'split' AND split_factor IS NOT NULL
          AND symbol IN ({placeholders})
          AND event_date > %s AND event_date <= %s
    """  # nosec B608 - only "%s" placeholders are interpolated; values are bound
    with conn.cursor() as cur:
        cur.execute(query, [*symbols, start_date, anchor_date])
        rows = cur.fetchall()
    splits = pd.DataFrame(rows, columns=["symbol", "event_date", "split_factor"])
    splits["event_date"] = pd.to_datetime(splits["event_date"])
    splits["split_factor"] = splits["split_factor"].astype(float)
    return splits


def split_adjust(prices: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """
    Back-adjust long-format daily prices for splits.

    Args:
        prices: Rows with ``trading_date``, ``symbol`` and any of open/high/low/close/volume
        splits: Rows with ``symbol``, ``event_date``, ``split_factor`` (the splits to
            apply, i.e. those up to the anchor date)

    Returns:
        A copy with prices divided, and volume multiplied, by the product of the factors
        of all later splits of the same symbol. Price and volume columns are always float.
    """
    adjusted = prices.copy()
    dates = pd.to_datetime(adjusted["trading_date"]) if not adjusted.empty else None
    factor = pd.Series(1.0, index=adjusted.index)
    for split in splits.itertuples(index=False):
        before = (adjusted["symbol"] == split.symbol) & (dates < pd.Timestamp(split.event_date))
        factor[before] *= float(split.split_factor)

    for column in PRICE_COLUMNS:
        if column in adjusted:
            adjusted[column] = adjusted[column].astype(float) / factor
    if "volume" in adjusted:
        adjusted["volume"] = adjusted["volume"].astype(float) * factor

    _warn_on_suspect_split_days(adjusted, splits)
    return adjusted


def _warn_on_suspect_split_days(adjusted: pd.DataFrame, splits: pd.DataFrame) -> None:
    """Log split days whose adjusted close still moves more than SUSPECT_SPLIT_DAY_MOVE."""
    if splits.empty or "close" not in adjusted:
        return
    for split in splits.itertuples(index=False):
        rows = adjusted[adjusted["symbol"] == split.symbol].sort_values("trading_date")
        dates = pd.to_datetime(rows["trading_date"])
        on_day = rows[dates == pd.Timestamp(split.event_date)]
        before = rows[dates < pd.Timestamp(split.event_date)]
        if on_day.empty or before.empty:
            continue
        move = on_day["close"].iloc[0] / before["close"].iloc[-1] - 1
        if abs(move) > SUSPECT_SPLIT_DAY_MOVE:
            logger.warning(
                f"{split.symbol} split on {pd.Timestamp(split.event_date).date()} "
                f"(factor {split.split_factor:g}) still moves {move:+.0%} after adjustment"
            )
