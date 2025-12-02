"""
Analysis History Manager - Track voter component details for ML/analysis.

Issue #444: Track MACD/RSI component details and voting outcomes.

Provides:
- SQLite storage of analysis details (MACD histogram, RSI value, signals, etc.)
- Link to trade_history table when trades are executed
- Query interface for ML training data and strategy analysis
- Timeframe-specific analysis tracking

Database Schema:
- analysis_history: Voter component details with optional trade linkage
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnalysisRecord:
    """Record of a single trading analysis with voter component details."""

    timestamp: str
    ticker: str
    timeframe: str
    macd_histogram: Optional[float]
    macd_signal: Optional[str]  # BUY/SELL/HOLD
    rsi_value: Optional[float]
    rsi_signal: Optional[str]  # BUY/SELL/HOLD
    final_signal: str  # BUY/SELL/HOLD
    confidence: float
    action_taken: str  # "executed", "rejected", "hold_signal"
    trade_id: Optional[int] = None
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "ticker": self.ticker,
            "timeframe": self.timeframe,
            "macd_histogram": self.macd_histogram,
            "macd_signal": self.macd_signal,
            "rsi_value": self.rsi_value,
            "rsi_signal": self.rsi_signal,
            "final_signal": self.final_signal,
            "confidence": self.confidence,
            "action_taken": self.action_taken,
            "trade_id": self.trade_id,
        }


class AnalysisHistoryManager:
    """
    Manage analysis history database for ML training and strategy analysis.

    Stores detailed voter component data (MACD, RSI, signals) from each analysis,
    enabling ML model training and strategy optimization.
    """

    DEFAULT_DB_PATH = "data/user.db"

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize AnalysisHistoryManager.

        Args:
            db_path: Path to user.db (default: data/user.db)
        """
        if db_path:
            self.db_path = db_path
        else:
            # Use default path relative to project root
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            self.db_path = str(data_dir / "user.db")

        self._ensure_table()
        logger.info(f"AnalysisHistoryManager initialized with database: {self.db_path}")

    def _ensure_table(self):
        """Create analysis_history table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    macd_histogram REAL,
                    macd_signal TEXT,
                    rsi_value REAL,
                    rsi_signal TEXT,
                    final_signal TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    action_taken TEXT NOT NULL,
                    trade_id INTEGER,
                    FOREIGN KEY (trade_id) REFERENCES trade_history(id)
                )
            """
            )

            # Create indexes for common queries
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_ticker
                ON analysis_history(ticker)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_timestamp
                ON analysis_history(timestamp)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_signal
                ON analysis_history(final_signal)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_analysis_timeframe
                ON analysis_history(timeframe)
            """
            )

            conn.commit()
            logger.debug("analysis_history table and indexes ensured")

        finally:
            conn.close()

    def record_analysis(
        self,
        ticker: str,
        timeframe: str,
        macd_histogram: Optional[float],
        macd_signal: Optional[str],
        rsi_value: Optional[float],
        rsi_signal: Optional[str],
        final_signal: str,
        confidence: float,
        action_taken: str,
        trade_id: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> int:
        """
        Record an analysis to the database.

        Args:
            ticker: Stock symbol
            timeframe: Timeframe used (e.g., "1d", "1h", "5m")
            macd_histogram: MACD histogram value
            macd_signal: MACD signal (BUY/SELL/HOLD)
            rsi_value: RSI value
            rsi_signal: RSI signal (BUY/SELL/HOLD)
            final_signal: Final consensus signal (BUY/SELL/HOLD)
            confidence: Confidence percentage (0.0-1.0)
            action_taken: What happened ("executed", "rejected", "hold_signal")
            trade_id: Optional link to trade_history.id
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Database ID of the inserted record
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO analysis_history (
                    timestamp, ticker, timeframe,
                    macd_histogram, macd_signal,
                    rsi_value, rsi_signal,
                    final_signal, confidence, action_taken, trade_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    timestamp,
                    ticker,
                    timeframe,
                    macd_histogram,
                    macd_signal,
                    rsi_value,
                    rsi_signal,
                    final_signal,
                    confidence,
                    action_taken,
                    trade_id,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.debug(f"Recorded analysis for {ticker}: {final_signal} (id={record_id})")
            return record_id

        finally:
            conn.close()

    def get_analysis_by_ticker(
        self, ticker: str, limit: Optional[int] = None
    ) -> List[AnalysisRecord]:
        """
        Get all analyses for a specific ticker.

        Args:
            ticker: Stock symbol
            limit: Optional limit on number of records

        Returns:
            List of AnalysisRecord objects
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = """
                SELECT * FROM analysis_history
                WHERE ticker = ?
                ORDER BY timestamp DESC
            """
            if limit:
                query += f" LIMIT {limit}"

            cursor = conn.execute(query, (ticker,))
            rows = cursor.fetchall()

            return [
                AnalysisRecord(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    ticker=row["ticker"],
                    timeframe=row["timeframe"],
                    macd_histogram=row["macd_histogram"],
                    macd_signal=row["macd_signal"],
                    rsi_value=row["rsi_value"],
                    rsi_signal=row["rsi_signal"],
                    final_signal=row["final_signal"],
                    confidence=row["confidence"],
                    action_taken=row["action_taken"],
                    trade_id=row["trade_id"],
                )
                for row in rows
            ]

        finally:
            conn.close()

    def get_signal_statistics(self, ticker: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics on signal frequency and outcomes.

        Args:
            ticker: Optional ticker to filter by

        Returns:
            Dictionary with signal counts and percentages
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Build params tuple
            params = (ticker,) if ticker else ()

            # Count by final signal
            if ticker:
                query_signal = """
                    SELECT final_signal, COUNT(*) as count
                    FROM analysis_history
                    WHERE ticker = ?
                    GROUP BY final_signal
                """
            else:
                query_signal = """
                    SELECT final_signal, COUNT(*) as count
                    FROM analysis_history
                    GROUP BY final_signal
                """
            cursor = conn.execute(query_signal, params)
            signal_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Count by MACD signal
            if ticker:
                query_macd = """
                    SELECT macd_signal, COUNT(*) as count
                    FROM analysis_history
                    WHERE ticker = ?
                    GROUP BY macd_signal
                """
            else:
                query_macd = """
                    SELECT macd_signal, COUNT(*) as count
                    FROM analysis_history
                    GROUP BY macd_signal
                """
            cursor = conn.execute(query_macd, params)
            macd_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Count by RSI signal
            if ticker:
                query_rsi = """
                    SELECT rsi_signal, COUNT(*) as count
                    FROM analysis_history
                    WHERE ticker = ?
                    GROUP BY rsi_signal
                """
            else:
                query_rsi = """
                    SELECT rsi_signal, COUNT(*) as count
                    FROM analysis_history
                    GROUP BY rsi_signal
                """
            cursor = conn.execute(query_rsi, params)
            rsi_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Count by action taken
            if ticker:
                query_action = """
                    SELECT action_taken, COUNT(*) as count
                    FROM analysis_history
                    WHERE ticker = ?
                    GROUP BY action_taken
                """
            else:
                query_action = """
                    SELECT action_taken, COUNT(*) as count
                    FROM analysis_history
                    GROUP BY action_taken
                """
            cursor = conn.execute(query_action, params)
            action_counts = {row[0]: row[1] for row in cursor.fetchall()}

            total = sum(signal_counts.values())

            return {
                "total_analyses": total,
                "signal_counts": signal_counts,
                "macd_counts": macd_counts,
                "rsi_counts": rsi_counts,
                "action_counts": action_counts,
                "ticker": ticker,
            }

        finally:
            conn.close()

    def get_analyses_by_timeframe(
        self, timeframe: str, limit: Optional[int] = None
    ) -> List[AnalysisRecord]:
        """
        Get analyses for a specific timeframe.

        Args:
            timeframe: Timeframe to filter by (e.g., "1d", "1h")
            limit: Optional limit on number of records

        Returns:
            List of AnalysisRecord objects
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = """
                SELECT * FROM analysis_history
                WHERE timeframe = ?
                ORDER BY timestamp DESC
            """
            if limit:
                query += f" LIMIT {limit}"

            cursor = conn.execute(query, (timeframe,))
            rows = cursor.fetchall()

            return [
                AnalysisRecord(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    ticker=row["ticker"],
                    timeframe=row["timeframe"],
                    macd_histogram=row["macd_histogram"],
                    macd_signal=row["macd_signal"],
                    rsi_value=row["rsi_value"],
                    rsi_signal=row["rsi_signal"],
                    final_signal=row["final_signal"],
                    confidence=row["confidence"],
                    action_taken=row["action_taken"],
                    trade_id=row["trade_id"],
                )
                for row in rows
            ]

        finally:
            conn.close()

    def get_ml_training_data(self, executed_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get data suitable for ML training.

        Args:
            executed_only: If True, only return analyses that resulted in trades

        Returns:
            List of dictionaries with feature data
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            query = """
                SELECT
                    ticker, timeframe,
                    macd_histogram, macd_signal,
                    rsi_value, rsi_signal,
                    final_signal, confidence,
                    action_taken, trade_id
                FROM analysis_history
            """

            if executed_only:
                query += " WHERE action_taken = 'executed'"

            query += " ORDER BY timestamp DESC"

            cursor = conn.execute(query)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

        finally:
            conn.close()

    def link_analysis_to_trade(self, analysis_id: int, trade_id: int) -> bool:
        """
        Link an analysis record to a trade in trade_history.

        Args:
            analysis_id: ID of analysis_history record
            trade_id: ID of trade_history record

        Returns:
            True if successful
        """
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE analysis_history
                SET trade_id = ?
                WHERE id = ?
            """,
                (trade_id, analysis_id),
            )
            conn.commit()
            logger.debug(f"Linked analysis {analysis_id} to trade {trade_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to link analysis to trade: {e}")
            return False

        finally:
            conn.close()
