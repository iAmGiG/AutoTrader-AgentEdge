"""
Trade History Cache Mixin for TradingCacheManager.

Issue #510: Extracted from sqlite_cache.py for modularity.
Contains trade archival and analytics methods.
"""

import json
import logging
import sqlite3
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)


class TradeCacheMixin:
    """
    Mixin providing trade history cache functionality.

    Requires:
        - self.db_path: Path to SQLite database
        - self._write_lock: Threading lock for write operations
        - self.logger: Logger instance
    """

    def archive_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        Archive completed trade to database for analytics.

        This implements the hybrid storage approach:
        - Active trades in JSON (fast, simple)
        - Completed trades in database (analytics, TradingView-style charts)

        Args:
            trade_data: Dictionary with trade details including:
                - trade_id (required): Unique trade identifier
                - symbol (required): Stock symbol
                - entry_date (required): Entry datetime ISO format
                - entry_price (required): Entry price
                - quantity (required): Number of shares
                - exit_date: Exit datetime ISO format
                - exit_price: Exit price
                - exit_reason: Reason for exit
                - initial_stop_loss: Initial stop loss price
                - initial_take_profit: Initial take profit price
                - realized_pnl: Realized profit/loss
                - realized_pnl_pct: Realized P&L percentage
                - strategy_name: Strategy used (e.g., "VoterAgent")
                - signal_strength: Signal strength (BULLISH/BEARISH/NEUTRAL)
                - signal_confidence: Confidence level 0.0-1.0
                - broker_account: Broker account identifier
                - notes: Additional metadata (dict, will be JSON serialized)

        Returns:
            True if archived successfully, False otherwise
        """
        try:
            required_fields = ["trade_id", "symbol", "entry_date", "entry_price", "quantity"]
            for field in required_fields:
                if field not in trade_data:
                    self.logger.error(f"Missing required field: {field}")
                    return False

            notes = trade_data.get("notes")
            if isinstance(notes, dict):
                notes = json.dumps(notes)

            with self._write_lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(
                        """
                        INSERT INTO trade_history (
                            trade_id, symbol, asset_type,
                            entry_date, entry_price, entry_order_id, quantity,
                            exit_date, exit_price, exit_order_id, exit_reason,
                            initial_stop_loss, initial_take_profit,
                            final_stop_loss, final_take_profit, stop_adjustments,
                            realized_pnl, realized_pnl_pct,
                            max_profit_pct, max_drawdown_pct, holding_period_hours,
                            strategy_name, signal_strength, signal_confidence,
                            entry_slippage_pct, exit_slippage_pct, commission_paid,
                            broker_account, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            trade_data["trade_id"],
                            trade_data["symbol"].upper(),
                            trade_data.get("asset_type", "stock"),
                            trade_data["entry_date"],
                            trade_data["entry_price"],
                            trade_data.get("entry_order_id"),
                            trade_data["quantity"],
                            trade_data.get("exit_date"),
                            trade_data.get("exit_price"),
                            trade_data.get("exit_order_id"),
                            trade_data.get("exit_reason"),
                            trade_data.get("initial_stop_loss"),
                            trade_data.get("initial_take_profit"),
                            trade_data.get("final_stop_loss"),
                            trade_data.get("final_take_profit"),
                            trade_data.get("stop_adjustments", 0),
                            trade_data.get("realized_pnl"),
                            trade_data.get("realized_pnl_pct"),
                            trade_data.get("max_profit_pct"),
                            trade_data.get("max_drawdown_pct"),
                            trade_data.get("holding_period_hours"),
                            trade_data.get("strategy_name"),
                            trade_data.get("signal_strength"),
                            trade_data.get("signal_confidence"),
                            trade_data.get("entry_slippage_pct"),
                            trade_data.get("exit_slippage_pct"),
                            trade_data.get("commission_paid"),
                            trade_data.get("broker_account", "alpaca_paper"),
                            notes,
                        ),
                    )
                    conn.commit()

            self.logger.info(
                f"Archived trade {trade_data['trade_id']} to database: "
                f"{trade_data['symbol']} P&L: {trade_data.get('realized_pnl', 'N/A')}"
            )
            return True

        except sqlite3.IntegrityError as e:
            self.logger.warning(f"Trade {trade_data.get('trade_id')} already archived: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to archive trade: {e}", exc_info=True)
            return False

    def get_trade_history(
        self,
        symbol: str = None,
        start_date: str = None,
        end_date: str = None,
        strategy: str = None,
        broker_account: str = None,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        Query trade history for analytics and TradingView-style visualizations.

        Args:
            symbol: Filter by symbol (None = all symbols)
            start_date: Filter by entry date >= start_date (YYYY-MM-DD)
            end_date: Filter by entry date <= end_date (YYYY-MM-DD)
            strategy: Filter by strategy name
            broker_account: Filter by broker account
            limit: Limit number of results (None = all)

        Returns:
            DataFrame with trade history
        """
        try:
            query = "SELECT * FROM trade_history WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())
            if start_date:
                query += " AND entry_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND entry_date <= ?"
                params.append(end_date)
            if strategy:
                query += " AND strategy_name = ?"
                params.append(strategy)
            if broker_account:
                query += " AND broker_account = ?"
                params.append(broker_account)

            query += " ORDER BY entry_date DESC"

            if limit:
                query += f" LIMIT {int(limit)}"

            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query(query, conn, params=params)

            self.logger.debug(f"Retrieved {len(df)} trades from history")
            return df

        except Exception as e:
            self.logger.error(f"Error querying trade history: {e}")
            return pd.DataFrame()

    def get_trade_stats(self, symbol: str = None, strategy: str = None) -> Dict[str, Any]:
        """
        Get aggregated trading statistics.

        Args:
            symbol: Filter by symbol (None = all symbols)
            strategy: Filter by strategy (None = all strategies)

        Returns:
            Dictionary with trading statistics
        """
        try:
            where_clauses = []
            params = []

            if symbol:
                where_clauses.append("symbol = ?")
                params.append(symbol.upper())
            if strategy:
                where_clauses.append("strategy_name = ?")
                params.append(strategy)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            with sqlite3.connect(self.db_path) as conn:
                stats_query = f"""
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                        SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                        SUM(realized_pnl) as total_pnl,
                        AVG(realized_pnl) as avg_pnl,
                        AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END) as avg_win,
                        AVG(CASE WHEN realized_pnl < 0 THEN realized_pnl END) as avg_loss,
                        SUM(CASE WHEN realized_pnl > 0 THEN realized_pnl ELSE 0 END) as gross_profit,
                        SUM(CASE WHEN realized_pnl < 0 THEN ABS(realized_pnl) ELSE 0 END) as gross_loss,
                        AVG(holding_period_hours) as avg_holding_hours
                    FROM trade_history
                    WHERE {where_sql}
                """  # nosec B608
                row = conn.execute(stats_query, params).fetchone()

            total_trades = row[0] or 0
            winning_trades = row[1] or 0
            losing_trades = row[2] or 0
            total_pnl = row[3] or 0.0
            avg_pnl = row[4] or 0.0
            avg_win = row[5] or 0.0
            avg_loss = row[6] or 0.0
            gross_profit = row[7] or 0.0
            gross_loss = row[8] or 0.0
            avg_holding_hours = row[9] or 0.0

            win_rate_pct = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

            return {
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": losing_trades,
                "win_rate_pct": win_rate_pct,
                "total_pnl": total_pnl,
                "avg_pnl": avg_pnl,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": profit_factor,
                "avg_holding_hours": avg_holding_hours,
            }

        except Exception as e:
            self.logger.error(f"Error getting trade stats: {e}")
            return {}
