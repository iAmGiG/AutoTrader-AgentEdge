"""
GEX Regime Overlay for Research Strategies.

Shared logic for filtering and sizing positions based on dealer gamma exposure regime.
Used by all three research strategies (#544, #545, #546) as the paper's central A/B test.

Data source: options_daily_summary.regime (2020-2025, 1505 SPY trading days)
Regimes: bullish_gamma, bearish_gamma, neutral
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
    """

    # Position scaling by regime
    REGIME_SCALES = {
        "bullish_gamma": 1.0,  # Full position — stable, mean-reverting
        "bearish_gamma": 0.75,  # Reduced — volatile, trend-following
        "neutral": 0.5,  # Half position — low conviction
    }

    def __init__(self, db_connection):
        self._conn = db_connection
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

    def get_regime(self, symbol: str, as_of_date) -> Optional[str]:
        """Get GEX regime for a symbol on a given date.

        Returns:
            'bullish_gamma', 'bearish_gamma', 'neutral', or None if no data.
        """
        df = self._load_regime_data(symbol)
        if isinstance(as_of_date, str):
            as_of_date = pd.Timestamp(as_of_date)
        elif isinstance(as_of_date, datetime):
            as_of_date = pd.Timestamp(as_of_date)

        # Find the most recent regime on or before as_of_date
        mask = df.index <= as_of_date
        if mask.any():
            return df.loc[mask, "regime"].iloc[-1]
        return None

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
        df = self._load_regime_data(symbol)
        if isinstance(as_of_date, str):
            as_of_date = pd.Timestamp(as_of_date)

        mask = df.index <= as_of_date
        if mask.any():
            return float(df.loc[mask, "total_gex"].iloc[-1])
        return None
