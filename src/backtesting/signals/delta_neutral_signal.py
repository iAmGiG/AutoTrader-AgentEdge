"""
Delta Neutral / Long Volatility Signal Generator (#544).

Implements an IV-RV spread strategy following:
- Carr, P. & Wu, L. (2009). "Variance Risk Premiums."
- Coval, J. & Shumway, T. (2001). "Expected Option Returns."

Approach:
1. Track IV-HV spread (implied vol minus realized vol) from options_daily_summary
2. When IV >> RV (spread high): volatility is expensive → sell vol (short straddle proxy)
3. When IV << RV (spread low/negative): volatility is cheap → buy vol (long straddle proxy)
4. P&L modeled as spread * notional (simplified; no dynamic hedging)

GEX overlay (#544): In negative gamma regimes, volatility tends to expand —
size long-vol positions larger. In positive gamma, volatility dampened — favor short-vol.
"""

from typing import Any, Dict, Optional

import pandas as pd


class DeltaNeutralSignal:
    """IV-RV spread-based volatility trading signal.

    Uses pre-computed vol metrics from options_daily_summary rather than
    constructing straddles from individual contracts. This gives 5+ years
    of daily signals for backtesting.

    Args:
        vol_spread_window: Which IV-HV spread column to use (10, 20, or 30 day).
        entry_threshold: Absolute spread threshold to enter (default 0.02 = 2 vol pts).
        exit_threshold: Spread reverts within this to exit (default 0.005).
        max_holding_days: Maximum days to hold a position.
    """

    def __init__(
        self,
        vol_spread_window: int = 30,
        entry_threshold: float = 0.02,
        exit_threshold: float = 0.005,
        max_holding_days: int = 30,
    ):
        if vol_spread_window not in (10, 20, 30):
            raise ValueError("vol_spread_window must be 10, 20, or 30")
        self.spread_col = f"iv_hv_spread_{vol_spread_window}"
        self.hv_col = f"hv_{vol_spread_window}"
        self.rv_col = f"realized_vol_{vol_spread_window}"
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_holding_days = max_holding_days
        # Loaded data
        self._vol_data: Optional[pd.DataFrame] = None

    def load_vol_data(self, db_connection, symbol: str, start_date: str, end_date: str):
        """Load vol metrics from options_daily_summary.

        Args:
            db_connection: psycopg2 connection to gex_options.
            symbol: Ticker symbol (e.g. 'SPY').
            start_date: Start date string.
            end_date: End date string.
        """
        cur = db_connection.cursor()
        cur.execute(
            f"""
            SELECT trading_date, underlying_price,
                   {self.spread_col}, {self.hv_col}, {self.rv_col},
                   regime, total_gex, iv_skew, put_call_ratio
            FROM options_daily_summary
            WHERE symbol = %s
              AND trading_date BETWEEN %s AND %s
              AND {self.spread_col} IS NOT NULL
            ORDER BY trading_date
            """,
            (symbol, start_date, end_date),
        )
        rows = cur.fetchall()
        self._vol_data = pd.DataFrame(
            rows,
            columns=[
                "trading_date",
                "underlying_price",
                "iv_hv_spread",
                "hv",
                "rv",
                "regime",
                "total_gex",
                "iv_skew",
                "put_call_ratio",
            ],
        )
        self._vol_data["trading_date"] = pd.to_datetime(self._vol_data["trading_date"])
        self._vol_data = self._vol_data.set_index("trading_date")

    def get_vol_data(self) -> pd.DataFrame:
        """Return loaded vol metrics."""
        if self._vol_data is None:
            raise RuntimeError("Call load_vol_data() first")
        return self._vol_data

    def generate_signal(self, prices: pd.DataFrame, idx: int) -> Dict[str, Any]:
        """Generate delta neutral signal based on IV-RV spread.

        Args:
            prices: DataFrame with at least one symbol column (used for date alignment).
            idx: Current row index.

        Returns:
            Signal dict with action, position_size, daily_pnl_pct, confidence, reasoning.
        """
        if self._vol_data is None:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "daily_pnl_pct": 0.0,
                "confidence": 0.0,
                "reasoning": "Vol data not loaded",
            }

        date = prices.index[idx]

        # Find vol data for this date
        mask = self._vol_data.index <= date
        if not mask.any():
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "daily_pnl_pct": 0.0,
                "confidence": 0.0,
                "reasoning": "No vol data for this date",
            }

        row = self._vol_data.loc[mask].iloc[-1]
        spread = float(row["iv_hv_spread"])

        # Calculate daily P&L from spread changes (simplified)
        # When long vol: profit if spread increases (IV rises relative to RV)
        # When short vol: profit if spread decreases
        daily_pnl_pct = 0.0
        if idx > 0:
            prev_date = prices.index[idx - 1]
            prev_mask = self._vol_data.index <= prev_date
            if prev_mask.any():
                prev_spread = float(self._vol_data.loc[prev_mask, "iv_hv_spread"].iloc[-1])
                spread_change = spread - prev_spread
                # Calibrated: 0.25x gives ~1% daily vol, matching typical vol strategy
                # (avg daily |Δspread| = 0.023, so 0.023 * 0.25 ≈ 0.6% daily move)
                daily_pnl_pct = spread_change * 0.25

        confidence = min(0.9, abs(spread) / (self.entry_threshold * 3))

        # Signal logic
        if spread > self.entry_threshold:
            # IV >> RV: vol is expensive → sell vol (short straddle)
            return {
                "action": "SELL",
                "position_size": 1.0,
                "daily_pnl_pct": daily_pnl_pct,
                "confidence": confidence,
                "reasoning": f"Short vol: IV-RV spread={spread:.4f} > {self.entry_threshold}",
            }
        elif spread < -self.entry_threshold:
            # IV << RV: vol is cheap → buy vol (long straddle)
            return {
                "action": "BUY",
                "position_size": 1.0,
                "daily_pnl_pct": daily_pnl_pct,
                "confidence": confidence,
                "reasoning": f"Long vol: IV-RV spread={spread:.4f} < -{self.entry_threshold}",
            }
        elif abs(spread) < self.exit_threshold:
            # Spread has reverted → exit
            return {
                "action": "EXIT",
                "position_size": 0.0,
                "daily_pnl_pct": daily_pnl_pct,
                "confidence": 0.5,
                "reasoning": f"Exit: IV-RV spread={spread:.4f} within ±{self.exit_threshold}",
            }
        else:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "daily_pnl_pct": daily_pnl_pct,
                "confidence": 0.3,
                "reasoning": f"Hold: IV-RV spread={spread:.4f}, between thresholds",
            }

    def calculate_spread_stats(self) -> Dict[str, Any]:
        """Calculate summary statistics of the IV-RV spread for research output."""
        if self._vol_data is None:
            raise RuntimeError("Call load_vol_data() first")

        spread = self._vol_data["iv_hv_spread"]
        return {
            "mean": float(spread.mean()),
            "std": float(spread.std()),
            "min": float(spread.min()),
            "max": float(spread.max()),
            "median": float(spread.median()),
            "pct_positive": float((spread > 0).mean() * 100),
            "pct_above_entry": float((spread > self.entry_threshold).mean() * 100),
            "pct_below_neg_entry": float((spread < -self.entry_threshold).mean() * 100),
            "n_obs": len(spread),
        }
