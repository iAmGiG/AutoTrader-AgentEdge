"""
MACD+RSI Signal Generator for GEX Regime Research (#531).

Wraps the validated calculate_macd() and calculate_rsi() from
src/trading/instruments/indicators.py into the research signal interface.
Uses shift(1) to prevent look-ahead bias: yesterday's indicator → today's execution.

P&L model: actual daily price returns when in position (not synthetic).
"""

import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

# Import indicators directly via spec loader to avoid triggering
# src.trading.__init__ which has Alpaca SDK import conflicts
_indicators_path = Path(__file__).parent.parent.parent / "trading" / "instruments" / "indicators.py"
_spec = importlib.util.spec_from_file_location("indicators", _indicators_path)
_indicators = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_indicators)
calculate_macd = _indicators.calculate_macd
calculate_rsi = _indicators.calculate_rsi
calculate_voting_consensus = _indicators.calculate_voting_consensus


class MACDRSISignal:
    """MACD(13/34/8) + RSI(14/30/70) consensus signal for research backtesting.

    Args:
        fast: MACD fast EMA period (default 13).
        slow: MACD slow EMA period (default 34).
        signal_period: MACD signal EMA period (default 8).
        rsi_period: RSI period (default 14).
        rsi_oversold: RSI oversold threshold (default 30).
        rsi_overbought: RSI overbought threshold (default 70).
    """

    def __init__(
        self,
        fast: int = 13,
        slow: int = 34,
        signal_period: int = 8,
        rsi_period: int = 14,
        rsi_oversold: int = 30,
        rsi_overbought: int = 70,
    ):
        self.fast = fast
        self.slow = slow
        self.signal_period = signal_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self._signals_cache: Optional[pd.Series] = None
        self._prices_id: Optional[int] = None

    def _compute_signals(self, prices: pd.Series) -> pd.Series:
        """Compute shifted consensus signal series (cached).

        Returns a boolean Series where True = bullish consensus,
        shifted by 1 to prevent look-ahead bias.
        """
        prices_id = id(prices)
        if self._signals_cache is not None and self._prices_id == prices_id:
            return self._signals_cache

        macd_data = calculate_macd(prices, self.fast, self.slow, self.signal_period)
        rsi_data = calculate_rsi(prices, self.rsi_period, self.rsi_oversold, self.rsi_overbought)
        voting = calculate_voting_consensus(macd_data, rsi_data)

        # shift(1): yesterday's signal drives today's execution
        self._signals_cache = voting["consensus"].shift(1).fillna(False)
        self._prices_id = prices_id
        return self._signals_cache

    def generate_signal(self, prices: pd.DataFrame, idx: int) -> Dict[str, Any]:
        """Generate MACD+RSI signal for the research backtester.

        Args:
            prices: DataFrame with symbol columns. The first column is used for signals.
            idx: Current row index.

        Returns:
            Signal dict with action, position_size, daily_pnl_pct, confidence, reasoning.
        """
        symbol = prices.columns[0]
        price_series = prices[symbol]

        if idx < self.slow + 5:
            return {
                "action": "HOLD",
                "position_size": 0.0,
                "daily_pnl_pct": 0.0,
                "confidence": 0.0,
                "reasoning": "Insufficient warmup data",
            }

        consensus = self._compute_signals(price_series)

        # Daily P&L from actual price returns
        daily_pnl_pct = 0.0
        if idx > 0:
            daily_pnl_pct = (
                price_series.iloc[idx] - price_series.iloc[idx - 1]
            ) / price_series.iloc[idx - 1]

        is_bullish = bool(consensus.iloc[idx]) if idx < len(consensus) else False

        if is_bullish:
            return {
                "action": "BUY",
                "position_size": 1.0,
                "daily_pnl_pct": daily_pnl_pct,
                "confidence": 0.7,
                "reasoning": "MACD+RSI consensus bullish (shifted)",
            }
        else:
            return {
                "action": "EXIT",
                "position_size": 0.0,
                "daily_pnl_pct": 0.0,
                "confidence": 0.3,
                "reasoning": "No consensus — flat",
            }
