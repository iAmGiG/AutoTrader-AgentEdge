"""
Split adjustment for equity_prices_daily.

The table stores raw prices: ``adjusted_close`` equals ``close`` and ``daily_return`` is
raw, so a split shows up as a one-day move of the split ratio (AAPL 2020-08-31 -74%,
XLK and XLE 2025-12-05 -50%). ``gex.corporate_events`` lists the splits:
``event_date`` is the first trading day at the new price (checked against the price
jump for 131 of the 133 splits inside the price history; the other two are reverse
splits on days the stock also moved a lot) and ``split_factor`` is new shares per old
share (4.0 for a 4-for-1 split, 0.1 for a 1-for-10 reverse split).

Prices are back-adjusted to the scale at the end of the requested window: every price
before a split is divided by its factor and volume multiplied by it, so returns and
dollar volume are continuous. Splits after the window end are not applied.
"""

from typing import Iterable, Optional

import pandas as pd

PRICE_COLUMNS = ("open", "high", "low", "close")


def load_splits(conn, symbols: Iterable[str], end_date: Optional[str] = None) -> pd.DataFrame:
    """Splits for the symbols (columns: symbol, event_date, split_factor), up to end_date."""
    symbols = list(symbols)
    if not symbols:
        return pd.DataFrame(columns=["symbol", "event_date", "split_factor"])
    placeholders = ",".join(["%s"] * len(symbols))
    query = f"""
        SELECT symbol, event_date, split_factor
        FROM gex.corporate_events
        WHERE event_type = 'split' AND split_factor IS NOT NULL
          AND symbol IN ({placeholders})
    """  # nosec B608 - only "%s" placeholders are interpolated; symbols are bound
    params = list(symbols)
    if end_date is not None:
        query += " AND event_date <= %s"
        params.append(end_date)
    cur = conn.cursor()
    cur.execute(query, params)
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
        splits: Rows with ``symbol``, ``event_date``, ``split_factor`` (only splits that
            should apply, i.e. on or before the end of the window)

    Returns:
        A copy with prices divided, and volume multiplied, by the product of the factors
        of all later splits of the same symbol
    """
    adjusted = prices.copy()
    if splits.empty or adjusted.empty:
        return adjusted

    dates = pd.to_datetime(adjusted["trading_date"])
    factor = pd.Series(1.0, index=adjusted.index)
    for split in splits.itertuples(index=False):
        before = (adjusted["symbol"] == split.symbol) & (dates < pd.Timestamp(split.event_date))
        factor[before] *= float(split.split_factor)

    for column in PRICE_COLUMNS:
        if column in adjusted:
            adjusted[column] = adjusted[column].astype(float) / factor
    if "volume" in adjusted:
        adjusted["volume"] = adjusted["volume"].astype(float) * factor
    return adjusted
