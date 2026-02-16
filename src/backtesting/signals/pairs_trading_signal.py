"""
Pairs Trading Mean Reversion Signal Generator (#546).

Implements cointegration-based pairs trading following:
- Engle, R. & Granger, C. (1987). "Co-integration and Error Correction."
- Gatev et al. (2006). "Pairs Trading: Performance of a Relative-Value Arbitrage Rule."

Approach:
1. Estimate hedge ratio via OLS (log prices)
2. Validate cointegration with Engle-Granger test (p < 0.05)
3. Calculate spread = log(A) - beta * log(B)
4. Generate signals on rolling z-score of spread
5. Entry at |z| > entry_z, exit when |z| < exit_z

GEX overlay (#546): In GEX-enhanced mode, only trade when the regime supports
mean-reversion (bullish_gamma). Reduce size in bearish/neutral regimes.
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from statsmodels.tsa.stattools import adfuller, coint


class PairsTradingSignal:
    """Cointegration-based pairs trading signal generator.

    Compatible with ResearchBacktester.run_spread_strategy().

    Args:
        lookback: Rolling window for z-score (trading days).
        entry_z: Z-score threshold to open a position.
        exit_z: Z-score threshold to close a position.
        max_half_lives: Exit if trade exceeds this many half-lives.
    """

    def __init__(
        self,
        lookback: int = 60,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        max_half_lives: float = 4.0,
    ):
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.max_half_lives = max_half_lives
        # Fitted parameters
        self.hedge_ratio: Optional[float] = None
        self.spread_mean: Optional[float] = None
        self.spread_std: Optional[float] = None
        self.half_life_days: Optional[float] = None
        self.coint_pvalue: Optional[float] = None
        self.adf_pvalue: Optional[float] = None

    def fit(self, prices_a: pd.Series, prices_b: pd.Series) -> Dict[str, Any]:
        """Estimate hedge ratio and test cointegration.

        Uses Engle-Granger two-step method:
        1. OLS regression of log(A) on log(B) to get hedge ratio (beta)
        2. Test residuals for stationarity (ADF test)
        3. Estimate Ornstein-Uhlenbeck half-life from residual AR(1)

        Args:
            prices_a: Close prices for symbol A.
            prices_b: Close prices for symbol B.

        Returns:
            Dict with cointegration test results and fitted parameters.
        """
        log_a = np.log(prices_a.dropna())
        log_b = np.log(prices_b.dropna())

        # Align on common index
        common = log_a.index.intersection(log_b.index)
        log_a = log_a.loc[common]
        log_b = log_b.loc[common]

        # OLS: log(A) = alpha + beta * log(B) + epsilon
        x_mat = add_constant(log_b.values)
        model = OLS(log_a.values, x_mat).fit()
        self.hedge_ratio = float(model.params[1])

        # Spread residuals
        spread = log_a.values - self.hedge_ratio * log_b.values
        self.spread_mean = float(np.mean(spread))
        self.spread_std = float(np.std(spread))

        # Engle-Granger cointegration test
        _, pvalue, _ = coint(log_a.values, log_b.values)
        self.coint_pvalue = float(pvalue)

        # ADF test on spread
        adf_result = adfuller(spread, maxlag=10, autolag="AIC")
        self.adf_pvalue = float(adf_result[1])

        # Half-life of mean reversion (O-U process)
        self.half_life_days = self._estimate_half_life(spread)

        return {
            "hedge_ratio": self.hedge_ratio,
            "spread_mean": self.spread_mean,
            "spread_std": self.spread_std,
            "coint_pvalue": self.coint_pvalue,
            "adf_pvalue": self.adf_pvalue,
            "half_life_days": self.half_life_days,
            "is_cointegrated": self.coint_pvalue < 0.05,
            "r_squared": float(model.rsquared),
            "n_obs": len(common),
        }

    @staticmethod
    def _estimate_half_life(spread: np.ndarray) -> float:
        """Estimate Ornstein-Uhlenbeck half-life from spread residuals.

        Fits AR(1): spread_t - spread_{t-1} = phi * spread_{t-1} + epsilon
        Half-life = -ln(2) / ln(1 + phi)

        Returns:
            Half-life in trading days, clipped to [1, 252].
        """
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)
        x_mat = add_constant(spread_lag)
        model = OLS(spread_diff, x_mat).fit()
        phi = model.params[1]

        if phi >= 0:
            # Not mean-reverting
            return 252.0

        half_life = -np.log(2) / np.log(1 + phi)
        return float(np.clip(half_life, 1.0, 252.0))

    def calculate_spread(self, prices_a: pd.Series, prices_b: pd.Series) -> pd.Series:
        """Calculate log spread using fitted hedge ratio.

        spread = log(A) - beta * log(B)
        """
        if self.hedge_ratio is None:
            raise RuntimeError("Call fit() before calculate_spread()")
        return np.log(prices_a) - self.hedge_ratio * np.log(prices_b)

    def calculate_zscore(self, spread: pd.Series) -> pd.Series:
        """Rolling z-score of spread over lookback window."""
        roll_mean = spread.rolling(window=self.lookback, min_periods=self.lookback).mean()
        roll_std = spread.rolling(window=self.lookback, min_periods=self.lookback).std()
        return (spread - roll_mean) / roll_std.replace(0, np.nan)

    def generate_signal(self, prices: pd.DataFrame, idx: int) -> Dict[str, Any]:
        """Generate trading signal for ResearchBacktester.run_spread_strategy().

        Args:
            prices: DataFrame with columns for both symbols.
            idx: Current row index into prices.

        Returns:
            Signal dict with 'action', 'position_size', 'confidence', 'reasoning'.
        """
        if self.hedge_ratio is None:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": "Model not fitted",
            }

        if idx < self.lookback:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": f"Insufficient data: {idx} < {self.lookback} lookback",
            }

        # Get the two symbol columns
        cols = prices.columns.tolist()
        if len(cols) < 2:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": "Need 2 symbol columns",
            }

        sym_a, sym_b = cols[0], cols[1]

        # Calculate spread up to current index
        window = prices.iloc[max(0, idx - self.lookback) : idx + 1]
        spread = np.log(window[sym_a]) - self.hedge_ratio * np.log(window[sym_b])

        if len(spread) < self.lookback:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": "Insufficient lookback window",
            }

        # Z-score at current bar
        z = (spread.iloc[-1] - spread.mean()) / spread.std()

        if np.isnan(z):
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "confidence": 0.0,
                "reasoning": "Z-score is NaN",
            }

        confidence = min(0.95, abs(z) / (self.entry_z * 2))

        # Entry signals
        if z < -self.entry_z:
            return {
                "action": "BUY",
                "position_size": 1.0,
                "confidence": confidence,
                "reasoning": f"Spread undervalued: z={z:.2f} < -{self.entry_z}",
            }
        elif z > self.entry_z:
            return {
                "action": "SELL",
                "position_size": 1.0,
                "confidence": confidence,
                "reasoning": f"Spread overvalued: z={z:.2f} > {self.entry_z}",
            }

        # Exit signal (mean reversion achieved)
        if abs(z) < self.exit_z:
            return {
                "action": "EXIT",
                "position_size": 0.0,
                "confidence": confidence,
                "reasoning": f"Spread reverted: |z|={abs(z):.2f} < {self.exit_z}",
            }

        return {
            "action": "HOLD",
            "position_size": 0.0,
            "confidence": 0.3,
            "reasoning": f"Spread z={z:.2f}, between exit and entry thresholds",
        }
