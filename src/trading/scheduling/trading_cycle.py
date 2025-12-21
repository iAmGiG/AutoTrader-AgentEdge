#!/usr/bin/env python3
"""
Cost-Efficient Trade Cycle - Minimal API calls using GTC orders

Core Principle: Let the broker do the work via GTC orders, minimize LLM/API calls.
- Morning routine: 9:20 AM ET - reconcile, adjust stops, generate report
- Evening routine: 3:50 PM ET - EOD review and preparation
- Batch all API calls to minimize costs
- JSON is for humans, broker is truth

Refactored in #439 to use extracted components:
- LocalStateManager: JSON persistence
- BrokerStateCache: Broker state caching
- StateReconciler: Reconciliation logic
- ReportGenerator: Report formatting
"""

import logging
import os
from dataclasses import asdict
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)

from config_defaults.trading_config import TradingConfig

from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData
from src.trading.broker.alpaca_trading_client import (
    AlpacaAccountMonitor,
    AlpacaOrderManager,
)
from src.trading.orders.trailing_stop_manager import TrailingStopManager
from src.trading.positions.position_tracker import PositionTracker
from src.trading.state.broker_state_cache import BrokerStateCache
from src.trading.state.local_state_manager import LocalStateManager
from src.trading.state.state_reconciler import (
    Discrepancy,
    PositionAlertSummary,
    StateReconciler,
    StopAdjustment,
)
from src.trading.utils.report_generator import ReportGenerator, RoutineType
from src.utils.date_utils import get_datetime_now

# GTT (Good-Till-Triggered) integration - Issue #340
try:
    from src.trading.gtt.action_executor import get_action_executor
    from src.trading.gtt.trailing_stop_bridge import (
        restore_trailing_stops_from_gtt,
        sync_all_trailing_stops,
    )
    from src.trading.gtt.trigger_evaluator import get_trigger_evaluator

    GTT_AVAILABLE = True
except ImportError:
    GTT_AVAILABLE = False

# Re-export dataclasses for backward compatibility
__all__ = [
    "CostEfficientTradeCycle",
    "Discrepancy",
    "StopAdjustment",
    "PositionAlertSummary",
    "RoutineType",
]


class CostEfficientTradeCycle:
    """
    Redesigned for minimal API calls using GTC orders.

    Strategy:
    - Two scheduled routines per day (morning/evening)
    - Single API call to get all positions/orders per routine
    - Batch all modifications into single API calls
    - Generate human-readable reports for oversight
    - Crash recovery rebuilds state from broker truth

    Components (extracted in #439):
    - LocalStateManager: JSON state persistence
    - BrokerStateCache: Cached broker state with TTL
    - StateReconciler: Reconciliation and alert logic
    - ReportGenerator: Human-readable reports
    """

    def __init__(self, state_file: str = None):
        # Load path configuration from config_defaults/paths_config.yaml
        config_path = os.path.join("config_defaults", "paths_config.yaml")
        try:
            with open(config_path) as f:
                paths_config = yaml.safe_load(f)
                self.paths = paths_config
                logger.info(f"Loaded paths config from {config_path}")
        except FileNotFoundError:
            logger.warning(f"Paths config not found at {config_path}, using hardcoded defaults")
            self.paths = {
                "state_files": {"cost_efficient": "state/cost_efficient_positions.json"},
                "report_templates": {"daily_routine": "reports/daily/{date}_{routine_type}.md"},
            }

        # Use config value if state_file not explicitly provided
        if state_file is None:
            state_file = self.paths.get("state_files", {}).get(
                "cost_efficient", "state/cost_efficient_positions.json"
            )

        # Initialize market data and account services
        self.market_data = AlpacaMarketData()
        self.account_monitor = AlpacaAccountMonitor(mode="paper")
        self.order_manager = AlpacaOrderManager(mode="paper")

        # Load trading config
        self.config = TradingConfig()

        # Initialize position tracker for alerts
        self.position_tracker = PositionTracker(
            take_profit_pct=self.config.get_risk_config("take_profit"),
            stop_loss_pct=self.config.get_risk_config("stop_loss"),
            alert_cooldown_seconds=300,  # 5 minutes between alerts
        )

        # Initialize trailing stop manager for dynamic stop adjustments
        self.trailing_stop_manager = TrailingStopManager(
            order_manager=None,  # We handle broker calls separately via batch_modify_orders()
            config=self.config,
        )

        # Restore multi-day trailing stops from GTT persistence (Phase 3, Issue #340)
        if GTT_AVAILABLE:
            try:
                restore_result = restore_trailing_stops_from_gtt(self.trailing_stop_manager)
                if restore_result["restored"] > 0:
                    logger.info(
                        f"Restored {restore_result['restored']} trailing stops from GTT persistence"
                    )
            except Exception as e:
                logger.warning(f"Failed to restore trailing stops from GTT: {e}")

        # Initialize extracted components
        self.local_state_manager = LocalStateManager(
            state_file=state_file,
            position_tracker=self.position_tracker,
        )

        self.broker_cache = BrokerStateCache(
            account_monitor=self.account_monitor,
            check_alerts_callback=self._check_position_alerts_internal,
            cache_ttl_seconds=60,
            alert_refresh_interval=300,
        )

        self.reconciler = StateReconciler(
            config=self.config,
            trailing_stop_manager=self.trailing_stop_manager,
            position_tracker=self.position_tracker,
        )

        self.report_generator = ReportGenerator()

        logger.info("CostEfficientTradeCycle initialized with extracted components")

    # -------------------------------------------------------------------------
    # Backward-compatible property accessors
    # -------------------------------------------------------------------------

    @property
    def local_state(self) -> Dict[str, Any]:
        """Get local state dict (backward compatibility)."""
        return self.local_state_manager.state

    @local_state.setter
    def local_state(self, value: Dict[str, Any]):
        """Set local state dict (backward compatibility)."""
        self.local_state_manager.state = value

    @property
    def state_file(self) -> str:
        """Get state file path (backward compatibility)."""
        return self.local_state_manager.state_file

    # -------------------------------------------------------------------------
    # Backward-compatible method wrappers
    # -------------------------------------------------------------------------

    def load_local_state(self) -> Dict[str, Any]:
        """Load local JSON state (backward compatibility)."""
        return self.local_state_manager.reload()

    def save_local_state(self):
        """Save local state to JSON (backward compatibility)."""
        self.local_state_manager.save()

    def fetch_broker_state(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get broker state with caching (backward compatibility)."""
        return self.broker_cache.fetch(force_refresh)

    def invalidate_broker_cache(self):
        """Invalidate broker cache (backward compatibility)."""
        self.broker_cache.invalidate()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics (backward compatibility)."""
        return self.broker_cache.get_stats()

    def get_current_alerts(self) -> List[Any]:
        """Get cached alerts (backward compatibility)."""
        return self.broker_cache.get_current_alerts()

    def reconcile_state(self, broker_state: Dict[str, Any]) -> List[Discrepancy]:
        """Reconcile state (backward compatibility)."""
        discrepancies, updated_state = self.reconciler.reconcile(
            broker_state, self.local_state_manager.state
        )
        self.local_state_manager.state = updated_state
        return discrepancies

    def calculate_stop_adjustments(self, broker_state: Dict[str, Any]) -> List[StopAdjustment]:
        """Calculate stop adjustments (backward compatibility)."""
        adjustments, updated_state = self.reconciler.calculate_stop_adjustments(
            broker_state, self.local_state_manager.state
        )
        self.local_state_manager.state = updated_state
        return adjustments

    def check_position_alerts(self, broker_state: Dict[str, Any]) -> List[PositionAlertSummary]:
        """Check position alerts (backward compatibility)."""
        return self.reconciler.check_position_alerts(broker_state, self.local_state_manager.state)

    def _check_position_alerts_internal(self, broker_state: Dict[str, Any]) -> List[Any]:
        """Internal callback for broker cache alert refresh."""
        return self.reconciler.check_position_alerts(broker_state, self.local_state_manager.state)

    def generate_position_summaries(
        self, broker_state: Dict[str, Any], adjustments: List[StopAdjustment]
    ) -> List[Any]:
        """Generate position summaries (backward compatibility)."""
        return self.report_generator.generate_position_summaries(
            broker_state, self.local_state_manager.state, adjustments
        )

    def generate_routine_report(
        self,
        routine_type: RoutineType,
        broker_state: Dict[str, Any],
        discrepancies: List[Discrepancy],
        adjustments: List[StopAdjustment],
        alerts: List[PositionAlertSummary] = None,
        modification_results: Dict[str, Any] = None,
    ) -> str:
        """Generate trading report (backward compatibility)."""
        return self.report_generator.generate_routine_report(
            routine_type,
            broker_state,
            self.local_state_manager.state,
            discrepancies,
            adjustments,
            alerts,
            modification_results,
        )

    # -------------------------------------------------------------------------
    # Order execution (kept in main class as it handles broker communication)
    # -------------------------------------------------------------------------

    def batch_modify_orders(self, adjustments: List[StopAdjustment]) -> Dict[str, Any]:
        """
        Batch modify stop orders with enhanced logging.
        """
        if not adjustments:
            logger.info("No stop adjustments to execute")
            return {"success": True, "modifications": 0, "errors": []}

        logger.info(f"Executing {len(adjustments)} stop order modifications...")

        results = {"success": True, "modifications": 0, "errors": [], "details": []}

        for i, adjustment in enumerate(adjustments, 1):
            try:
                logger.info(f"[{i}/{len(adjustments)}] Modifying {adjustment.symbol} stop order...")
                logger.debug(f"  Order ID: {adjustment.order_id}")
                logger.debug(f"  Current stop: ${adjustment.current_stop:.2f}")
                logger.debug(f"  New stop: ${adjustment.new_stop:.2f}")
                logger.debug(f"  Reason: {adjustment.reason}")

                # Modify the stop order
                success = self.order_manager.modify_order(
                    order_id=adjustment.order_id, stop_price=adjustment.new_stop
                )

                if success:
                    results["modifications"] += 1
                    entry_price = (
                        self.local_state_manager.state.get("positions", {})
                        .get(adjustment.symbol, {})
                        .get("entry_price", 0)
                    )
                    profit_locked = adjustment.new_stop - float(entry_price)
                    detail_msg = (
                        f"✅ {adjustment.symbol}: Stop adjusted to ${adjustment.new_stop:.2f} "
                        f"(locking ${profit_locked:+.2f} profit)"
                    )
                    results["details"].append(detail_msg)
                    logger.info(detail_msg)
                else:
                    error_msg = f"Failed to modify {adjustment.symbol} stop order"
                    results["errors"].append(error_msg)
                    results["success"] = False
                    logger.error(error_msg)

            except Exception as e:
                error_msg = f"Error modifying {adjustment.symbol} stop: {e}"
                results["errors"].append(error_msg)
                logger.error(error_msg)
                logger.exception("Full exception details:")
                results["success"] = False

        summary = (
            f"Stop adjustment batch complete: "
            f"{results['modifications']}/{len(adjustments)} successful, "
            f"{len(results['errors'])} errors"
        )
        logger.info(summary)

        # Invalidate cache after modifying orders
        if results["modifications"] > 0:
            self.broker_cache.invalidate()

        return results

    # -------------------------------------------------------------------------
    # GTT (Good-Till-Triggered) Integration - Issue #340
    # -------------------------------------------------------------------------

    def check_gtt_triggers(self, broker_state: Dict[str, Any]) -> List[Any]:
        """
        Check GTT triggers against current prices.

        Args:
            broker_state: Current broker state with positions/prices

        Returns:
            List of ActionResult for triggers that fired
        """
        if not GTT_AVAILABLE:
            return []

        try:
            # Get current prices from broker state
            prices = {}
            for symbol, pos in broker_state.get("positions", {}).items():
                if "current_price" in pos:
                    prices[symbol] = pos["current_price"]
                elif "market_value" in pos and "quantity" in pos:
                    # Calculate from market value
                    qty = pos["quantity"]
                    if qty > 0:
                        prices[symbol] = pos["market_value"] / qty

            if not prices:
                logger.debug("No prices available for GTT check")
                return []

            # Evaluate triggers
            evaluator = get_trigger_evaluator()
            triggered = evaluator.evaluate_triggers_batch(prices)

            if not triggered:
                logger.debug("No GTT triggers fired")
                return []

            # Execute actions for triggered GTTs
            executor = get_action_executor()
            results = executor.execute_triggers_batch(triggered, prices)

            # Log summary
            success_count = sum(1 for r in results if r.success)
            logger.info(f"GTT: {len(triggered)} triggers fired, {success_count} actions executed")

            return results

        except Exception as e:
            logger.error(f"GTT check failed: {e}")
            return []

    def _format_gtt_results_for_report(self, gtt_results: List[Any]) -> List[str]:
        """Format GTT results for inclusion in routine report."""
        if not gtt_results:
            return []

        lines = [
            "",
            "## GTT Triggers Fired",
            "",
        ]

        for result in gtt_results:
            status = "+" if result.success else "x"
            lines.append(f"[{status}] Trigger {result.trigger_id}: {result.message}")

            details = result.details or {}
            if details.get("symbol"):
                lines.append(f"    Symbol: {details['symbol']}")
            if details.get("current_price"):
                lines.append(f"    Price: ${details['current_price']:.2f}")
            if details.get("oco_disabled"):
                lines.append(f"    OCO: Disabled {details['oco_disabled']} partner(s)")

        return lines

    # -------------------------------------------------------------------------
    # Trading routines
    # -------------------------------------------------------------------------

    def morning_routine(self) -> str:
        """
        Run once at 9:20 AM ET - before market open.
        Minimal API calls, maximum insight.
        """
        logger.info("Starting morning routine...")

        try:
            # Step 1: Single API call to get all positions/orders
            broker_state = self.fetch_broker_state()

            # Step 2: Reconcile with local JSON (no API calls)
            discrepancies = self.reconcile_state(broker_state)

            # Step 3: Check for position alerts (no API calls)
            alerts = self.check_position_alerts(broker_state)

            # Step 3.5: Check GTT triggers (no API calls) - Issue #340
            gtt_results = self.check_gtt_triggers(broker_state)

            # Step 4: Calculate stop adjustments needed (no API calls)
            adjustments = self.calculate_stop_adjustments(broker_state)

            # Step 5: Batch modify stops if needed (single API call)
            modification_results = None
            if adjustments:
                modification_results = self.batch_modify_orders(adjustments)

            # Step 5.5: Sync trailing stops to GTT for multi-day persistence (Phase 3, Issue #340)
            if GTT_AVAILABLE:
                try:
                    sync_result = sync_all_trailing_stops(self.trailing_stop_manager)
                    if sync_result["synced"] > 0:
                        logger.info(f"Synced {sync_result['synced']} trailing stops to GTT")
                except Exception as e:
                    logger.warning(f"Failed to sync trailing stops to GTT: {e}")

            # Step 6: Save updated local state
            self.local_state_manager.state["discrepancies"] = [asdict(d) for d in discrepancies]
            self.local_state_manager.save()

            # Step 7: Generate human report with alerts
            report = self.generate_routine_report(
                RoutineType.MORNING,
                broker_state,
                discrepancies,
                adjustments,
                alerts,
                modification_results,
            )

            # Append GTT results to report if any
            if gtt_results:
                gtt_lines = self._format_gtt_results_for_report(gtt_results)
                report += "\n" + "\n".join(gtt_lines)

            # Save report to file
            report_file = self._get_report_file_path("morning")
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report)

            logger.info(f"Morning routine complete. Report saved to {report_file}")
            return report

        except Exception as e:
            error_msg = f"Morning routine failed: {e}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

    def evening_routine(self) -> str:
        """
        Run once at 3:50 PM ET - before market close.
        Focus on EOD position review and preparation for next day.
        """
        logger.info("Starting evening routine...")

        try:
            # Similar structure to morning, but focus on EOD analysis
            broker_state = self.fetch_broker_state()
            discrepancies = self.reconcile_state(broker_state)

            # Check for position alerts
            alerts = self.check_position_alerts(broker_state)

            # Check GTT triggers - Issue #340
            gtt_results = self.check_gtt_triggers(broker_state)

            # Sync trailing stops to GTT for multi-day persistence (Phase 3, Issue #340)
            if GTT_AVAILABLE:
                try:
                    sync_result = sync_all_trailing_stops(self.trailing_stop_manager)
                    if sync_result["synced"] > 0:
                        logger.info(f"Synced {sync_result['synced']} trailing stops to GTT")
                except Exception as e:
                    logger.warning(f"Failed to sync trailing stops to GTT: {e}")

            self.local_state_manager.save()

            report = self.generate_routine_report(
                RoutineType.EVENING, broker_state, discrepancies, [], alerts
            )

            # Append GTT results to report if any
            if gtt_results:
                gtt_lines = self._format_gtt_results_for_report(gtt_results)
                report += "\n" + "\n".join(gtt_lines)

            # Save report to file
            report_file = self._get_report_file_path("evening")
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report)

            logger.info(f"Evening routine complete. Report saved to {report_file}")
            return report

        except Exception as e:
            error_msg = f"Evening routine failed: {e}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

    def recover_from_crash(self) -> str:
        """
        Rebuild state from broker, minimal API calls.
        Use when system restarts or local state is corrupted.
        """
        logger.info("Starting crash recovery...")

        try:
            # One API call to get everything
            broker_state = self.fetch_broker_state()

            # Reset local state for recovery
            self.local_state_manager.reset_for_recovery()

            # Auto-discover all positions
            for symbol, broker_pos in broker_state["positions"].items():
                self.local_state_manager.set_position(
                    symbol,
                    {
                        "entry_price": broker_pos["entry_price"],
                        "quantity": broker_pos["quantity"],
                        "entry_time": "UNKNOWN",
                        "source": "CRASH_RECOVERY",
                        "stop_price": None,  # Will need human input
                        "target_price": None,  # Will need human input
                    },
                )

            self.local_state_manager.save()

            # Generate recovery report
            recovery_lines = [
                f"# Crash Recovery Report - {get_datetime_now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"Recovered {len(broker_state['positions'])} positions",
                f"Recovered {len(broker_state['orders'])} order groups",
                "",
                "## Recovered Positions",
            ]

            for symbol, pos in self.local_state_manager.positions.items():
                recovery_lines.append(
                    f"- {symbol}: {pos['quantity']} shares @ ${pos['entry_price']:.2f}"
                )

            recovery_lines.extend(
                [
                    "",
                    "⚠️ **MANUAL ACTION REQUIRED:**",
                    "- Review all positions for accuracy",
                    "- Set stop_price and target_price for each position",
                    "- Verify entry times if needed for tax reporting",
                    "",
                ]
            )

            report = "\n".join(recovery_lines)

            # Save recovery report
            report_file = self._get_report_file_path("recovery")
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report)

            logger.info(f"Crash recovery complete. Report saved to {report_file}")
            return report

        except Exception as e:
            error_msg = f"Crash recovery failed: {e}"
            logger.error(error_msg)
            return f"❌ {error_msg}"

    def _get_report_file_path(self, routine_type: str) -> str:
        """Get unique report file path with counter for multiple runs per day."""
        now = get_datetime_now()
        date_str = now.strftime("%Y-%m-%d")

        template = self.paths.get("report_templates", {}).get(
            "daily_routine", "reports/daily/{date}_{routine_type}.md"
        )
        base_name = template.format(date=date_str, routine_type=routine_type).replace(".md", "")

        # Check for existing files and append counter if needed
        report_file = f"{base_name}.md"
        counter = 1
        while os.path.exists(report_file):
            counter += 1
            report_file = f"{base_name}_{counter}.md"

        return report_file


def main():
    """Demo the cost-efficient trade cycle"""
    print("=== Cost-Efficient Trade Cycle Demo ===")

    try:
        cycle = CostEfficientTradeCycle()

        print("\n1. Running morning routine...")
        morning_report = cycle.morning_routine()
        print(morning_report)

        print("\n" + "=" * 50)
        print("Morning routine complete!")
        print("Next: Run evening routine at 3:50 PM ET")

    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
