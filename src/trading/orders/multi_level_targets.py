"""
Multi-Level Price Targets (Issue #372)

Extends partial exit functionality to support N price targets with
configurable distribution strategies and ATR-based target calculation.

Features:
- Dynamic number of targets (1-5)
- Equal, progressive, and custom distribution
- ATR-based target calculation (integrates with #366)
- Order splitting for existing positions
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.trading.instruments.entry_planning import calculate_atr
from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


class DistributionStrategy(Enum):
    """Distribution strategies for splitting position across targets."""

    EQUAL = "equal"  # 33/33/34 for 3 targets
    PROGRESSIVE = "progressive"  # 50/30/20 decreasing
    INVERSE = "inverse"  # 20/30/50 increasing
    CUSTOM = "custom"  # User-defined ratios


@dataclass
class PriceTarget:
    """Represents a single price target within multi-level exit strategy."""

    target_number: int
    quantity: int
    target_price: float
    percentage_gain: float  # Percentage from entry
    order_id: Optional[str] = None
    status: str = "pending"  # pending, placed, filled, cancelled
    filled_at: Optional[str] = None
    filled_price: Optional[float] = None


@dataclass
class MultiLevelState:
    """Track multi-level target state for a position."""

    symbol: str
    entry_price: float
    total_quantity: int
    targets: List[PriceTarget] = field(default_factory=list)
    distribution: DistributionStrategy = DistributionStrategy.EQUAL
    stop_price: Optional[float] = None
    stop_order_id: Optional[str] = None
    atr_value: Optional[float] = None
    created_at: str = field(default_factory=now_iso)
    last_updated: str = field(default_factory=now_iso)

    def get_filled_quantity(self) -> int:
        """Get total filled quantity across all targets."""
        return sum(t.quantity for t in self.targets if t.status == "filled")

    def get_remaining_quantity(self) -> int:
        """Get remaining unfilled quantity."""
        return self.total_quantity - self.get_filled_quantity()

    def get_active_targets(self) -> List[PriceTarget]:
        """Get targets that are still active (pending or placed)."""
        return [t for t in self.targets if t.status in ("pending", "placed")]


class MultiLevelTargetManager:
    """
    Manages multi-level price targets for positions.

    Issue #372: Multi-Level Price Targets with Order Splitting

    Provides:
    - N configurable price targets (1-5)
    - Multiple distribution strategies
    - ATR-based target calculation
    - Splitting of existing orders
    """

    def __init__(
        self,
        order_manager,
        default_targets: int = 3,
        default_distribution: DistributionStrategy = DistributionStrategy.EQUAL,
    ):
        """
        Initialize multi-level target manager.

        Args:
            order_manager: OrderManager instance for broker operations
            default_targets: Default number of targets (1-5)
            default_distribution: Default distribution strategy
        """
        self.order_manager = order_manager
        self.default_targets = min(max(default_targets, 1), 5)
        self.default_distribution = default_distribution
        self.positions: Dict[str, MultiLevelState] = {}

        logger.info(
            f"MultiLevelTargetManager initialized: {self.default_targets} targets, "
            f"distribution={self.default_distribution.value}"
        )

    def calculate_targets(
        self,
        entry_price: float,
        total_quantity: int,
        num_targets: int = 3,
        distribution: DistributionStrategy = DistributionStrategy.EQUAL,
        target_percentages: Optional[List[float]] = None,
        base_percentage: float = 0.03,
    ) -> List[PriceTarget]:
        """
        Calculate price targets for a position.

        Args:
            entry_price: Entry price
            total_quantity: Total shares
            num_targets: Number of targets (1-5)
            distribution: Distribution strategy
            target_percentages: Custom percentages [0.03, 0.06, 0.10] for profit levels
            base_percentage: Starting percentage for equal/progressive distribution

        Returns:
            List of PriceTarget objects
        """
        num_targets = min(max(num_targets, 1), 5)

        # Calculate quantities per target
        quantities = self._calculate_quantities(total_quantity, num_targets, distribution)

        # Calculate price levels
        if target_percentages:
            percentages = target_percentages[:num_targets]
        else:
            percentages = self._calculate_percentages(num_targets, base_percentage)

        targets = []
        for i, (qty, pct) in enumerate(zip(quantities, percentages), start=1):
            target_price = round(entry_price * (1 + pct), 2)
            targets.append(
                PriceTarget(
                    target_number=i,
                    quantity=qty,
                    target_price=target_price,
                    percentage_gain=pct * 100,
                )
            )

        return targets

    def calculate_atr_targets(
        self,
        entry_price: float,
        total_quantity: int,
        ohlcv_data,
        num_targets: int = 3,
        distribution: DistributionStrategy = DistributionStrategy.EQUAL,
        atr_multipliers: Optional[List[float]] = None,
    ) -> List[PriceTarget]:
        """
        Calculate ATR-based price targets (Issue #366 integration).

        Args:
            entry_price: Entry price
            total_quantity: Total shares
            ohlcv_data: DataFrame with OHLCV data for ATR calculation
            num_targets: Number of targets (1-5)
            distribution: Distribution strategy
            atr_multipliers: ATR multipliers for each target [1.0, 2.0, 3.0]

        Returns:
            List of PriceTarget objects with ATR-based prices
        """
        num_targets = min(max(num_targets, 1), 5)

        # Calculate ATR from OHLCV data
        atr = calculate_atr(ohlcv_data["High"], ohlcv_data["Low"], ohlcv_data["Close"])
        current_atr = atr.iloc[-1]

        # Default ATR multipliers if not provided
        if atr_multipliers is None:
            atr_multipliers = [1.0, 2.0, 3.0, 4.0, 5.0][:num_targets]

        # Calculate quantities per target
        quantities = self._calculate_quantities(total_quantity, num_targets, distribution)

        targets = []
        for i, (qty, mult) in enumerate(zip(quantities, atr_multipliers), start=1):
            target_price = round(entry_price + (current_atr * mult), 2)
            pct_gain = ((target_price - entry_price) / entry_price) * 100
            targets.append(
                PriceTarget(
                    target_number=i,
                    quantity=qty,
                    target_price=target_price,
                    percentage_gain=round(pct_gain, 2),
                )
            )

        return targets

    def _calculate_quantities(
        self, total_quantity: int, num_targets: int, distribution: DistributionStrategy
    ) -> List[int]:
        """Calculate share quantities based on distribution strategy."""
        if num_targets == 1:
            return [total_quantity]

        if distribution == DistributionStrategy.EQUAL:
            ratios = [1.0 / num_targets] * num_targets
        elif distribution == DistributionStrategy.PROGRESSIVE:
            # Decreasing: larger first
            ratios = self._progressive_ratios(num_targets, decreasing=True)
        elif distribution == DistributionStrategy.INVERSE:
            # Increasing: smaller first
            ratios = self._progressive_ratios(num_targets, decreasing=False)
        else:
            ratios = [1.0 / num_targets] * num_targets

        # Convert ratios to quantities, ensuring all shares allocated
        quantities = []
        remaining = total_quantity
        for i, ratio in enumerate(ratios):
            if i == len(ratios) - 1:
                quantities.append(remaining)
            else:
                qty = max(1, int(total_quantity * ratio))
                quantities.append(qty)
                remaining -= qty

        return quantities

    def _progressive_ratios(self, num_targets: int, decreasing: bool = True) -> List[float]:
        """Generate progressive distribution ratios."""
        weights = list(range(num_targets, 0, -1)) if decreasing else list(range(1, num_targets + 1))
        total = sum(weights)
        return [w / total for w in weights]

    def _calculate_percentages(self, num_targets: int, base: float) -> List[float]:
        """Calculate target percentages with progressive spacing."""
        return [base * (i + 1) for i in range(num_targets)]

    def register_position(
        self,
        symbol: str,
        entry_price: float,
        total_quantity: int,
        num_targets: int = 3,
        distribution: DistributionStrategy = DistributionStrategy.EQUAL,
        target_percentages: Optional[List[float]] = None,
        stop_price: Optional[float] = None,
        ohlcv_data=None,
        use_atr: bool = False,
        atr_multipliers: Optional[List[float]] = None,
    ) -> Optional[MultiLevelState]:
        """
        Register a position for multi-level target management.

        Args:
            symbol: Ticker symbol
            entry_price: Entry price
            total_quantity: Total shares
            num_targets: Number of targets (1-5)
            distribution: Distribution strategy
            target_percentages: Custom percentage targets
            stop_price: Stop loss price
            ohlcv_data: OHLCV data for ATR-based targets
            use_atr: Whether to use ATR-based target calculation
            atr_multipliers: ATR multipliers if using ATR targets

        Returns:
            MultiLevelState if registered, None on error
        """
        if total_quantity < num_targets:
            logger.warning(
                f"Position {symbol} too small for {num_targets} targets "
                f"(qty={total_quantity}), using {total_quantity} targets"
            )
            num_targets = total_quantity

        # Calculate targets
        if use_atr and ohlcv_data is not None:
            targets = self.calculate_atr_targets(
                entry_price, total_quantity, ohlcv_data, num_targets, distribution, atr_multipliers
            )
        else:
            targets = self.calculate_targets(
                entry_price, total_quantity, num_targets, distribution, target_percentages
            )

        # Create state
        state = MultiLevelState(
            symbol=symbol,
            entry_price=entry_price,
            total_quantity=total_quantity,
            targets=targets,
            distribution=distribution,
            stop_price=stop_price,
        )

        self.positions[symbol] = state
        logger.info(f"Registered {symbol} for multi-level targets: {len(targets)} targets")

        return state

    def place_target_orders(self, symbol: str) -> Dict[str, Any]:
        """
        Place limit orders for all targets.

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with order placement results
        """
        if symbol not in self.positions:
            return {"error": f"No position found for {symbol}"}

        state = self.positions[symbol]
        results = {"symbol": symbol, "orders_placed": 0, "errors": []}

        for target in state.targets:
            if target.status != "pending":
                continue

            try:
                result = self.order_manager.place_limit_order(
                    symbol=symbol,
                    qty=target.quantity,
                    side="sell",
                    limit_price=target.target_price,
                )

                if "error" not in result:
                    target.order_id = result.get("id")
                    target.status = "placed"
                    results["orders_placed"] += 1
                    logger.info(
                        f"Placed target {target.target_number} for {symbol}: "
                        f"{target.quantity} @ ${target.target_price}"
                    )
                else:
                    results["errors"].append(f"Target {target.target_number}: {result['error']}")

            except Exception as e:
                results["errors"].append(f"Target {target.target_number}: {str(e)}")

        state.last_updated = now_iso()
        return results

    def split_existing_order(
        self,
        symbol: str,
        existing_order_id: str,
        entry_price: float,
        total_quantity: int,
        num_targets: int = 3,
        distribution: DistributionStrategy = DistributionStrategy.EQUAL,
    ) -> Dict[str, Any]:
        """
        Split an existing take-profit order into multiple targets.

        Args:
            symbol: Ticker symbol
            existing_order_id: ID of order to split
            entry_price: Entry price (for percentage calculation)
            total_quantity: Total position quantity
            num_targets: Number of targets to create
            distribution: Distribution strategy

        Returns:
            Dict with split operation results
        """
        results = {"symbol": symbol, "cancelled": False, "new_targets": 0, "errors": []}

        # Cancel existing order
        try:
            cancel_result = self.order_manager.cancel_order(existing_order_id)
            if "error" in cancel_result:
                results["errors"].append(f"Cancel failed: {cancel_result['error']}")
                return results
            results["cancelled"] = True
            logger.info(f"Cancelled existing order {existing_order_id} for split")
        except Exception as e:
            results["errors"].append(f"Cancel error: {str(e)}")
            return results

        # Register and place new targets
        state = self.register_position(
            symbol=symbol,
            entry_price=entry_price,
            total_quantity=total_quantity,
            num_targets=num_targets,
            distribution=distribution,
        )

        if state:
            place_results = self.place_target_orders(symbol)
            results["new_targets"] = place_results.get("orders_placed", 0)
            results["errors"].extend(place_results.get("errors", []))

        return results

    def get_position_summary(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get summary of multi-level target state for a position."""
        if symbol not in self.positions:
            return None

        state = self.positions[symbol]
        return {
            "symbol": symbol,
            "entry_price": state.entry_price,
            "total_quantity": state.total_quantity,
            "remaining_quantity": state.get_remaining_quantity(),
            "distribution": state.distribution.value,
            "targets": [
                {
                    "number": t.target_number,
                    "quantity": t.quantity,
                    "price": t.target_price,
                    "gain_pct": t.percentage_gain,
                    "status": t.status,
                    "order_id": t.order_id,
                }
                for t in state.targets
            ],
            "stop_price": state.stop_price,
            "created_at": state.created_at,
            "last_updated": state.last_updated,
        }

    def format_targets_display(self, symbol: str) -> str:
        """Format targets for CLI display."""
        summary = self.get_position_summary(symbol)
        if not summary:
            return f"No multi-level targets found for {symbol}"

        lines = [
            f"Multi-Level Targets for {symbol}:",
            f"Entry: ${summary['entry_price']:.2f} | Total: {summary['total_quantity']} shares",
            f"Distribution: {summary['distribution']}",
            "",
        ]

        for t in summary["targets"]:
            status_icon = {"pending": "⏳", "placed": "📝", "filled": "✅", "cancelled": "❌"}.get(
                t["status"], "?"
            )
            lines.append(
                f"  PT{t['number']}: {t['quantity']:>4} @ ${t['price']:.2f} "
                f"(+{t['gain_pct']:.1f}%) {status_icon}"
            )

        if summary["stop_price"]:
            lines.append(f"\nStop Loss: ${summary['stop_price']:.2f}")

        return "\n".join(lines)
