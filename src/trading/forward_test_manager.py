"""
Forward Test Manager - Track and monitor forward testing operations.

Issue #324: Forward Testing Protocol
Provides infrastructure for 30-day forward testing validation before live deployment.

This is a standalone testing framework, NOT a CLI interactive feature.
For on-demand backtesting from CLI, see separate issue (TBD).

Components:
- Signal tracking and recording
- Trade outcome monitoring
- Daily performance metrics
- Test state persistence
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Type of trading signal."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class TradeOutcome(Enum):
    """Outcome status of a trade."""

    PENDING = "pending"  # Trade placed, not yet filled
    FILLED = "filled"  # Order filled, position open
    CLOSED_WIN = "closed_win"  # Position closed at profit
    CLOSED_LOSS = "closed_loss"  # Position closed at loss
    CANCELLED = "cancelled"  # Order cancelled before fill


@dataclass
class SignalRecord:
    """Record of a generated trading signal."""

    timestamp: datetime
    symbol: str
    signal_type: SignalType
    confidence: float
    price: float
    indicators: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "confidence": self.confidence,
            "price": self.price,
            "indicators": self.indicators,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SignalRecord":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            symbol=data["symbol"],
            signal_type=SignalType(data["signal_type"]),
            confidence=data["confidence"],
            price=data["price"],
            indicators=data.get("indicators", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TradeRecord:
    """Record of a completed or in-progress trade."""

    trade_id: str
    symbol: str
    entry_time: datetime
    entry_price: float
    quantity: int
    side: str  # 'buy' or 'sell'

    # Exit information (None if still open)
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None

    # Performance metrics
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None

    # Order details
    stop_price: Optional[float] = None
    target_price: Optional[float] = None

    # Status
    outcome: TradeOutcome = TradeOutcome.PENDING

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "side": self.side,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "outcome": self.outcome.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TradeRecord":
        """Create from dictionary."""
        return cls(
            trade_id=data["trade_id"],
            symbol=data["symbol"],
            entry_time=datetime.fromisoformat(data["entry_time"]),
            entry_price=data["entry_price"],
            quantity=data["quantity"],
            side=data["side"],
            exit_time=datetime.fromisoformat(data["exit_time"]) if data.get("exit_time") else None,
            exit_price=data.get("exit_price"),
            pnl=data.get("pnl"),
            pnl_percent=data.get("pnl_percent"),
            stop_price=data.get("stop_price"),
            target_price=data.get("target_price"),
            outcome=TradeOutcome(data["outcome"]),
            metadata=data.get("metadata", {}),
        )


class ForwardTestManager:
    """
    Manage forward testing operations and state.

    Tracks:
    - All generated signals
    - All executed trades
    - Daily P&L
    - Test progress and status

    NOT a backtesting engine - this runs alongside live/paper trading
    to validate system performance before go-live decision.
    """

    def __init__(self, test_name: str, state_dir: Path = Path("state/forward_tests")):
        """
        Initialize forward test manager.

        Args:
            test_name: Unique name for this test run
            state_dir: Directory to store test state
        """
        self.test_name = test_name
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.state_dir / f"{test_name}_state.json"

        # Test metadata
        self.start_date: Optional[date] = None
        self.end_date: Optional[date] = None
        self.initial_capital: float = 10000.0

        # Collections
        self.signals: List[SignalRecord] = []
        self.trades: List[TradeRecord] = []
        self.daily_pnl: Dict[str, float] = {}  # date -> pnl

        # Load existing state if available
        self._load_state()

    def start_test(self, initial_capital: float = 10000.0):
        """
        Start a new forward test.

        Args:
            initial_capital: Starting capital for test
        """
        self.start_date = date.today()
        self.initial_capital = initial_capital
        logger.info(f"Started forward test '{self.test_name}' with ${initial_capital:,.2f}")
        self._save_state()

    def record_signal(
        self,
        symbol: str,
        signal_type: SignalType,
        confidence: float,
        price: float,
        indicators: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> SignalRecord:
        """
        Record a generated trading signal.

        Args:
            symbol: Ticker symbol
            signal_type: BUY, SELL, or HOLD
            confidence: Confidence score (0.0-1.0)
            price: Current price when signal generated
            indicators: Indicator values (MACD, RSI, etc.)
            metadata: Additional signal context

        Returns:
            Created SignalRecord
        """
        signal = SignalRecord(
            timestamp=datetime.now(),
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            price=price,
            indicators=indicators or {},
            metadata=metadata or {},
        )

        self.signals.append(signal)
        logger.info(
            f"Recorded {signal_type.value} signal for {symbol} @ "
            f"${price:.2f} (confidence: {confidence:.2%})"
        )

        self._save_state()
        return signal

    def record_trade(
        self,
        trade_id: str,
        symbol: str,
        entry_time: datetime,
        entry_price: float,
        quantity: int,
        side: str,
        stop_price: Optional[float] = None,
        target_price: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> TradeRecord:
        """
        Record a new trade entry.

        Args:
            trade_id: Unique trade identifier
            symbol: Ticker symbol
            entry_time: Time of entry
            entry_price: Entry price
            quantity: Number of shares
            side: 'buy' or 'sell'
            stop_price: Stop loss price
            target_price: Take profit price
            metadata: Additional trade context

        Returns:
            Created TradeRecord
        """
        trade = TradeRecord(
            trade_id=trade_id,
            symbol=symbol,
            entry_time=entry_time,
            entry_price=entry_price,
            quantity=quantity,
            side=side,
            stop_price=stop_price,
            target_price=target_price,
            outcome=TradeOutcome.FILLED,
            metadata=metadata or {},
        )

        self.trades.append(trade)
        logger.info(f"Recorded {side} trade for {symbol}: {quantity} @ ${entry_price:.2f}")

        self._save_state()
        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_time: datetime,
        exit_price: float,
        outcome: TradeOutcome = TradeOutcome.CLOSED_WIN,
    ):
        """
        Record trade exit/close.

        Args:
            trade_id: Trade to close
            exit_time: Exit timestamp
            exit_price: Exit price
            outcome: CLOSED_WIN or CLOSED_LOSS
        """
        trade = self._find_trade(trade_id)
        if not trade:
            logger.error(f"Trade {trade_id} not found")
            return

        trade.exit_time = exit_time
        trade.exit_price = exit_price
        trade.outcome = outcome

        # Calculate P&L
        if trade.side == "buy":
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
        else:  # sell/short
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity

        trade.pnl_percent = (trade.pnl / (trade.entry_price * trade.quantity)) * 100

        # Update daily P&L
        trade_date = exit_time.date().isoformat()
        self.daily_pnl[trade_date] = self.daily_pnl.get(trade_date, 0.0) + trade.pnl

        logger.info(
            f"Closed trade {trade_id}: {trade.symbol} "
            f"P&L=${trade.pnl:.2f} ({trade.pnl_percent:+.2f}%)"
        )

        self._save_state()

    def get_test_stats(self) -> Dict[str, Any]:
        """
        Get current test statistics.

        Returns:
            Dictionary of test metrics
        """
        closed_trades = [
            t
            for t in self.trades
            if t.outcome in (TradeOutcome.CLOSED_WIN, TradeOutcome.CLOSED_LOSS)
        ]

        total_trades = len(closed_trades)
        winning_trades = len([t for t in closed_trades if t.outcome == TradeOutcome.CLOSED_WIN])
        losing_trades = len([t for t in closed_trades if t.outcome == TradeOutcome.CLOSED_LOSS])

        total_pnl = sum(t.pnl for t in closed_trades if t.pnl is not None)
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0.0

        return {
            "test_name": self.test_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "days_running": (date.today() - self.start_date).days if self.start_date else 0,
            "initial_capital": self.initial_capital,
            "total_signals": len(self.signals),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "pnl_percent": (
                (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0.0
            ),
            "open_positions": len([t for t in self.trades if t.outcome == TradeOutcome.FILLED]),
        }

    def _find_trade(self, trade_id: str) -> Optional[TradeRecord]:
        """Find trade by ID."""
        for trade in self.trades:
            if trade.trade_id == trade_id:
                return trade
        return None

    def _save_state(self):
        """Persist test state to disk."""
        state = {
            "test_name": self.test_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "signals": [s.to_dict() for s in self.signals],
            "trades": [t.to_dict() for t in self.trades],
            "daily_pnl": self.daily_pnl,
        }

        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        """Load test state from disk if exists."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)

            self.start_date = (
                date.fromisoformat(state["start_date"]) if state.get("start_date") else None
            )
            self.end_date = date.fromisoformat(state["end_date"]) if state.get("end_date") else None
            self.initial_capital = state.get("initial_capital", 10000.0)

            self.signals = [SignalRecord.from_dict(s) for s in state.get("signals", [])]
            self.trades = [TradeRecord.from_dict(t) for t in state.get("trades", [])]
            self.daily_pnl = state.get("daily_pnl", {})

            logger.info(
                f"Loaded test state for '{self.test_name}': "
                f"{len(self.signals)} signals, {len(self.trades)} trades"
            )

        except Exception as e:
            logger.error(f"Failed to load test state: {e}")
