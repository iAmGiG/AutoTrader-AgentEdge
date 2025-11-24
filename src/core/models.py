"""
Core data models for the trading system.

These models define the data structures used throughout the application,
ensuring type safety and clear contracts between components.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Signal(Enum):
    """Trading signal types"""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class AssetType(Enum):
    """Asset types supported by the system"""

    STOCK = "stock"
    OPTION = "option"
    # Future: CRYPTO, FUTURES, etc.


class OrderType(Enum):
    """Order types"""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class TimeInForce(Enum):
    """Order time in force"""

    DAY = "day"
    GTC = "gtc"  # Good-til-canceled (our default)
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill


@dataclass
class TradeRequest:
    """
    Parsed user request for trade analysis.

    This is the output of InputParser and input to StrategyAnalyzer.
    """

    ticker: str
    action: str  # "review", "buy", "sell"
    request_type: str = "trade"  # "trade" or "status_query" (LLM-determined)
    quantity: Optional[int] = None
    price: Optional[float] = None
    asset_type: AssetType = AssetType.STOCK

    # Options-specific fields (for future #330)
    strike: Optional[float] = None
    expiration: Optional[datetime] = None
    option_type: Optional[str] = None  # "call" or "put"

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    raw_input: str = ""  # Original user input


@dataclass
class AnalysisResult:
    """
    Output of StrategyAnalyzer.

    Contains the trading signal, confidence, entry/exit levels, and reasoning.
    """

    signal: Signal
    confidence: float  # 0.0 to 1.0

    # Price levels
    entry_price: float
    stop_loss: float
    take_profit: float

    # Analysis details
    reasoning: List[str] = field(default_factory=list)  # Bullet points
    indicators: Dict[str, Any] = field(default_factory=dict)  # MACD, RSI, etc.

    # Metadata
    analyzer_name: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RiskAssessment:
    """
    Output of RiskManager.

    Contains risk evaluation and recommended position sizing.
    """

    approved: bool  # False = hard block, True = proceed (maybe with warnings)

    # Position sizing
    recommended_quantity: int
    portfolio_pct: float  # % of portfolio after transaction

    # Risk metrics
    max_loss_usd: float  # Based on stop-loss
    risk_reward_ratio: float  # Target gain / max loss

    # Warnings and information
    warnings: List[str] = field(default_factory=list)
    buying_power_available: float = 0.0
    existing_position_qty: int = 0  # If already holding this ticker

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradeSuggestion:
    """
    Combined suggestion presented to user.

    Merges AnalysisResult + RiskAssessment into actionable suggestion.
    """

    # From analysis
    signal: Signal
    confidence: float
    entry_price: float
    stop_loss: float
    take_profit: float
    reasoning: List[str]

    # From risk assessment
    recommended_quantity: int
    portfolio_pct: float
    max_loss_usd: float
    risk_reward_ratio: float
    warnings: List[str]

    # Order details
    ticker: str
    order_type: OrderType = OrderType.LIMIT
    time_in_force: TimeInForce = TimeInForce.GTC  # Always GTC

    # Metadata
    suggestion_id: str = ""  # Set by session store
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TradeDecision:
    """
    User's decision on a suggestion.

    Used to track approval/rejection and any modifications.
    """

    suggestion: TradeSuggestion
    approved: bool = False

    # Modifications (if user wants to adjust)
    modified_quantity: Optional[int] = None
    modified_entry: Optional[float] = None
    modified_stop: Optional[float] = None
    modified_target: Optional[float] = None

    # Session tracking
    session_id: str = ""
    user_id: str = "default"

    # Metadata
    decision_timestamp: Optional[datetime] = None


@dataclass
class OrderResult:
    """
    Result of order execution.

    Returned by ExecutionManager after placing orders.
    """

    success: bool

    # Order IDs (may have multiple for bracket orders)
    entry_order_id: Optional[str] = None
    stop_order_id: Optional[str] = None
    target_order_id: Optional[str] = None

    # Order details
    ticker: str = ""
    quantity: int = 0
    filled_price: Optional[float] = None

    # Status
    message: str = ""
    error: Optional[str] = None

    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionState:
    """
    Persistent session state.

    Allows resuming conversations and tracking history.
    """

    session_id: str
    user_id: str

    # History
    suggestions: List[TradeSuggestion] = field(default_factory=list)
    decisions: List[TradeDecision] = field(default_factory=list)
    orders: List[OrderResult] = field(default_factory=list)

    # State
    autonomy_level: int = 0  # 0 = confirm, 1 = auto

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
