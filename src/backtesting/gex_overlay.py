"""
GEX Regime Overlay for Research Strategies.

Shared logic for filtering and sizing positions based on dealer gamma exposure regime.
Used by all three research strategies (#544, #545, #546) as the paper's central A/B test.

Data source: options_daily_summary.regime (2008-2026, computed from end-of-day options data)
Regimes: bullish_gamma, bearish_gamma, neutral

Look-ahead: a day's regime is derived from that day's closing options data, so it is not
known until the close. ``lag_days=1`` (default) returns the regime from before the queried
date; ``lag_days=0`` returns the same-day regime and is look-ahead for same-day returns (#576).
"""

from datetime import datetime
from typing import Dict, Optional

import pandas as pd


class GEXOverlay:
    """GEX regime overlay for position filtering and sizing.

    Uses daily regime from options_daily_summary rather than intraday snapshots,
    giving 5+ years of history for backtesting.

    Args:
        db_connection: psycopg2 connection to gex_options database.
        lag_days: Number of regime observations to lag. 1 (default) uses the most recent
            regime strictly before the queried date; 0 allows the same-day regime.
    """

    # Position scaling by regime
    REGIME_SCALES = {
        "bullish_gamma": 1.0,  # Full position — stable, mean-reverting
        "bearish_gamma": 0.75,  # Reduced — volatile, trend-following
        "neutral": 0.5,  # Half position — low conviction
    }

    def __init__(self, db_connection, lag_days: int = 1):
        if lag_days < 0:
            raise ValueError("lag_days must be >= 0")
        self._conn = db_connection
        self.lag_days = lag_days
        self._cache: Dict[str, pd.DataFrame] = {}

    def _load_regime_data(self, symbol: str) -> pd.DataFrame:
        """Load full regime history for a symbol. Cached per session."""
        if symbol in self._cache:
            return self._cache[symbol]

        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT trading_date, regime, total_gex, zero_gamma_level
            FROM options_daily_summary
            WHERE symbol = %s AND regime IS NOT NULL
            ORDER BY trading_date
            """,
            (symbol,),
        )
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=["trading_date", "regime", "total_gex", "zero_gamma_level"])
        df["trading_date"] = pd.to_datetime(df["trading_date"])
        df = df.set_index("trading_date")
        self._cache[symbol] = df
        return df

    def _lagged_row(self, df: pd.DataFrame, as_of_date):
        """Row of ``df`` known at ``as_of_date`` after applying ``lag_days``; None if absent."""
        if isinstance(as_of_date, (str, datetime)):
            as_of_date = pd.Timestamp(as_of_date)
        if self.lag_days == 0:
            known = df[df.index <= as_of_date]
        else:
            known = df[df.index < as_of_date]
            known = known.iloc[: len(known) - (self.lag_days - 1)]
        return known.iloc[-1] if len(known) else None

    def get_regime(self, symbol: str, as_of_date) -> Optional[str]:
        """Get GEX regime for a symbol on a given date.

        Returns:
            'bullish_gamma', 'bearish_gamma', 'neutral', or None if no data.
        """
        row = self._lagged_row(self._load_regime_data(symbol), as_of_date)
        return None if row is None else row["regime"]

    def should_trade(self, symbol: str, as_of_date) -> bool:
        """Whether GEX regime supports trading (non-neutral)."""
        regime = self.get_regime(symbol, as_of_date)
        return regime in ("bullish_gamma", "bearish_gamma")

    def position_scale(self, symbol: str, as_of_date) -> float:
        """Position size multiplier based on regime.

        Returns:
            1.0 for bullish_gamma, 0.75 for bearish_gamma, 0.5 for neutral, 0.0 if no data.
        """
        regime = self.get_regime(symbol, as_of_date)
        if regime is None:
            return 0.0
        return self.REGIME_SCALES.get(regime, 0.5)

    def get_total_gex(self, symbol: str, as_of_date) -> Optional[float]:
        """Get total GEX value for a date (for regime-conditional analysis)."""
        row = self._lagged_row(self._load_regime_data(symbol), as_of_date)
        return None if row is None else float(row["total_gex"])
