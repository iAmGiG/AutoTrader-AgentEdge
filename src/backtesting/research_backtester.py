"""
Research Backtester for GEX-Enhanced Strategies.

Lightweight backtester that reads from PostgreSQL (equity_prices_daily, options chains,
GEX snapshots) instead of the SQLite cache. Supports spread-based P&L for pairs trading,
simplified options P&L for delta neutral, and correlation-spread P&L for dispersion.

Produces BacktestResults-compatible output for consistent metric comparison.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np
import pandas as pd
import psycopg2

from src.backtesting.gex_overlay import GEXOverlay
from src.backtesting.results import BacktestResults

DB_PARAMS = {"host": "localhost", "port": 5432, "user": "cregan1", "database": "gex_options"}


@dataclass
class SpreadPosition:
    """Track a pairs/spread position."""

    entry_date: str
    entry_spread: float
    direction: int  # +1 = long spread, -1 = short spread
    size: float = 1.0


class ResearchBacktester:
    """PostgreSQL-backed backtester for research strategies.

    Args:
        initial_capital: Starting capital (default $100K for research).
        commission_bps: Round-trip commission in basis points (default 2 bps).
    """

    def __init__(self, initial_capital: float = 100_000, commission_bps: float = 2.0):
        self.initial_capital = initial_capital
        self.commission_bps = commission_bps
        self._conn = None

    def _get_connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**DB_PARAMS)
        return self._conn

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()

    def fetch_equity_prices(
        self, symbols: List[str], start_date: str, end_date: str
    ) -> pd.DataFrame:
        """Fetch daily OHLCV from equity_prices_daily.

        Returns:
            DataFrame with columns: trading_date, symbol, open, high, low, close, volume
            Pivoted so each symbol's close is a column.
        """
        conn = self._get_connection()
        placeholders = ",".join(["%s"] * len(symbols))
        query = f"""
            SELECT trading_date, symbol, open, high, low, close, volume
            FROM equity_prices_daily
            WHERE symbol IN ({placeholders})
              AND trading_date BETWEEN %s AND %s
            ORDER BY trading_date, symbol
        """
        df = pd.read_sql_query(query, conn, params=(*symbols, start_date, end_date))
        df["trading_date"] = pd.to_datetime(df["trading_date"])
        return df

    def get_close_prices(self, symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
        """Get pivoted close prices (columns = symbols, index = dates)."""
        raw = self.fetch_equity_prices(symbols, start_date, end_date)
        pivot = raw.pivot(index="trading_date", columns="symbol", values="close")
        return pivot.dropna()

    def get_gex_overlay(self) -> GEXOverlay:
        """Create a GEXOverlay connected to this backtester's DB."""
        return GEXOverlay(self._get_connection())

    def run_spread_strategy(
        self,
        signal_fn: Callable[[pd.DataFrame, int], dict],
        prices: pd.DataFrame,
        symbol_a: str,
        symbol_b: str,
    ) -> BacktestResults:
        """Backtest a spread-based strategy (pairs trading).

        Args:
            signal_fn: Function(prices_df, row_index) -> signal dict.
            prices: DataFrame with symbol columns and date index.
            symbol_a: First symbol in pair.
            symbol_b: Second symbol in pair.

        Returns:
            BacktestResults with spread P&L metrics.
        """
        capital = self.initial_capital
        position: Optional[SpreadPosition] = None
        trades = []
        portfolio_values = [capital]

        for i in range(1, len(prices)):
            signal = signal_fn(prices, i)
            action = signal.get("action", "HOLD")
            spread_val = np.log(prices[symbol_a].iloc[i]) - np.log(prices[symbol_b].iloc[i])
            date_str = str(prices.index[i].date())

            if position is None and action in ("BUY", "SELL"):
                # Open position
                direction = 1 if action == "BUY" else -1
                size = signal.get("position_size", 1.0)
                position = SpreadPosition(
                    entry_date=date_str,
                    entry_spread=spread_val,
                    direction=direction,
                    size=size,
                )
                cost = capital * self.commission_bps / 10_000
                capital -= cost
                trades.append(
                    {
                        "date": date_str,
                        "action": action,
                        "shares": size,
                        "price": spread_val,
                        "commission": cost,
                    }
                )

            elif position is not None and action == "HOLD":
                # Check exit signal
                pass  # Hold position

            elif position is not None and (
                action == "EXIT"
                or (action == "BUY" and position.direction == -1)
                or (action == "SELL" and position.direction == 1)
            ):
                # Close position
                spread_pnl = (spread_val - position.entry_spread) * position.direction
                dollar_pnl = capital * position.size * spread_pnl
                cost = capital * self.commission_bps / 10_000
                capital += dollar_pnl - cost
                trades.append(
                    {
                        "date": date_str,
                        "action": "EXIT",
                        "shares": position.size,
                        "price": spread_val,
                        "commission": cost,
                    }
                )
                position = None

            portfolio_values.append(capital)

        # Close any remaining position at last price
        if position is not None:
            spread_val = np.log(prices[symbol_a].iloc[-1]) - np.log(prices[symbol_b].iloc[-1])
            spread_pnl = (spread_val - position.entry_spread) * position.direction
            capital += capital * position.size * spread_pnl
            portfolio_values[-1] = capital

        daily_returns = pd.Series(
            np.diff(portfolio_values) / np.array(portfolio_values[:-1]),
            index=prices.index[: len(portfolio_values) - 1],
        )

        return BacktestResults.from_trading_simulation(
            symbol=f"{symbol_a}/{symbol_b}",
            start_date=str(prices.index[0].date()),
            end_date=str(prices.index[-1].date()),
            initial_capital=self.initial_capital,
            final_value=capital,
            trades=trades,
            returns_series=daily_returns,
        )

    def run_daily_signal_strategy(
        self,
        signal_fn: Callable[[pd.DataFrame, int], dict],
        prices: pd.DataFrame,
        symbol: str,
    ) -> BacktestResults:
        """Backtest a daily signal strategy on a single symbol.

        Generic runner for delta neutral and dispersion strategies where
        signal_fn returns daily P&L estimates.

        Args:
            signal_fn: Function(prices_df, row_index) -> signal dict with
                       'action', 'position_size', 'daily_pnl_pct' keys.
            prices: DataFrame with at least one symbol column.
            symbol: Primary symbol for results labeling.
        """
        capital = self.initial_capital
        in_position = False
        trades = []
        portfolio_values = [capital]

        for i in range(1, len(prices)):
            signal = signal_fn(prices, i)
            action = signal.get("action", "HOLD")
            date_str = str(prices.index[i].date())
            pnl_pct = signal.get("daily_pnl_pct", 0.0)

            if action in ("BUY", "SELL") and not in_position:
                in_position = True
                cost = capital * self.commission_bps / 10_000
                capital -= cost
                trades.append(
                    {
                        "date": date_str,
                        "action": action,
                        "shares": signal.get("position_size", 1.0),
                        "price": prices[symbol].iloc[i] if symbol in prices.columns else 0,
                        "commission": cost,
                    }
                )

            if in_position:
                capital *= 1 + pnl_pct

            if action == "EXIT" and in_position:
                in_position = False
                cost = capital * self.commission_bps / 10_000
                capital -= cost
                trades.append(
                    {
                        "date": date_str,
                        "action": "EXIT",
                        "shares": 1.0,
                        "price": 0,
                        "commission": cost,
                    }
                )

            portfolio_values.append(capital)

        daily_returns = pd.Series(
            np.diff(portfolio_values) / np.array(portfolio_values[:-1]),
            index=prices.index[: len(portfolio_values) - 1],
        )

        return BacktestResults.from_trading_simulation(
            symbol=symbol,
            start_date=str(prices.index[0].date()),
            end_date=str(prices.index[-1].date()),
            initial_capital=self.initial_capital,
            final_value=capital,
            trades=trades,
            returns_series=daily_returns,
        )
