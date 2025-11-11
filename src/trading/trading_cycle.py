#!/usr/bin/env python3
"""
Cost-Efficient Trade Cycle - Minimal API calls using GTC orders

Core Principle: Let the broker do the work via GTC orders, minimize LLM/API calls.
- Morning routine: 9:20 AM ET - reconcile, adjust stops, generate report
- Evening routine: 3:50 PM ET - EOD review and preparation
- Batch all API calls to minimize costs
- JSON is for humans, broker is truth
"""

import sys
import os
import json
import logging
from datetime import datetime, time, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.data_sources.sources.market.alpaca_market_data import AlpacaMarketData
from src.trading.alpaca_trading_client import AlpacaAccountMonitor, AlpacaOrderManager
from src.trading_tools.position_tracker import PositionTracker, AlertType

logger = logging.getLogger(__name__)

@dataclass
class Discrepancy:
    """Represents a mismatch between local state and broker reality"""
    type: str  # UNKNOWN_POSITION, GHOST_POSITION, ORDER_MISMATCH
    symbol: str
    details: Dict[str, Any]
    action: str  # NEEDS_HUMAN_REVIEW, AUTO_FIXED, REMOVED_FROM_JSON
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH

@dataclass
class StopAdjustment:
    """Represents a stop order modification needed"""
    symbol: str
    order_id: str
    current_stop: float
    new_stop: float
    reason: str
    profit_percent: float


@dataclass
class PositionAlertSummary:
    """Summary of position alerts for reporting"""
    symbol: str
    alert_type: str
    severity: str
    message: str
    timestamp: str
    current_price: float
    details: Dict[str, Any]

@dataclass
class PositionSummary:
    """Summary of a position for reporting"""
    symbol: str
    entry_price: float
    current_price: float
    stop_price: float
    target_price: float
    quantity: int
    unrealized_pl: float
    unrealized_percent: float
    stop_action: str  # "No change", "Move to breakeven", etc.

class RoutineType(Enum):
    MORNING = "morning"
    EVENING = "evening"
    RECOVERY = "recovery"

class CostEfficientTradeCycle:
    """
    Redesigned for minimal API calls using GTC orders.
    
    Strategy:
    - Two scheduled routines per day (morning/evening)
    - Single API call to get all positions/orders per routine
    - Batch all modifications into single API calls
    - Generate human-readable reports for oversight
    - Crash recovery rebuilds state from broker truth
    """
    
    def __init__(self, state_file: str = "state/cost_efficient_positions.json"):
        self.state_file = state_file
        self.market_data = AlpacaMarketData()
        self.account_monitor = AlpacaAccountMonitor(mode="paper")
        self.order_manager = AlpacaOrderManager(mode="paper")

        # Initialize position tracker for alerts
        self.position_tracker = PositionTracker(
            take_profit_pct=0.08,
            stop_loss_pct=0.05,
            alert_cooldown_seconds=300  # 5 minutes between alerts
        )

        # Ensure state directory exists
        os.makedirs(os.path.dirname(state_file), exist_ok=True)

        # Load local state
        self.local_state = self.load_local_state()

        logger.info("CostEfficientTradeCycle initialized with alert monitoring")
    
    def load_local_state(self) -> Dict[str, Any]:
        """Load local JSON state (for human reference)"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                # Restore position tracker with alert history
                if 'position_tracker_state' in state:
                    try:
                        self.position_tracker.restore_from_dict(state['position_tracker_state'])
                        logger.info("Restored position tracker with alert history")
                    except Exception as e:
                        logger.warning(f"Failed to restore position tracker state: {e}")

                return state
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state file: {e}")
                return {"positions": {}, "last_update": None, "discrepancies": []}
        return {"positions": {}, "last_update": None, "discrepancies": []}
    
    def save_local_state(self):
        """Save local state to JSON including position tracker with alert history"""
        self.local_state["last_update"] = datetime.now().isoformat()

        # Persist position tracker state (including alert history)
        self.local_state["position_tracker_state"] = self.position_tracker.to_dict()

        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.local_state, f, indent=2)
            logger.debug(f"Saved local state with {len(self.position_tracker.positions)} tracked positions")
        except IOError as e:
            logger.error(f"Failed to save state: {e}")
    
    def fetch_broker_state(self) -> Dict[str, Any]:
        """
        Single API call to get all positions and orders from broker.
        This is the source of truth.
        """
        try:
            # Get all positions (one API call)
            positions = self.account_monitor.get_positions()
            
            # Get all orders (one API call)  
            orders = self.account_monitor.get_orders(status='open')
            
            # Get account info (one API call)
            account = self.account_monitor.get_account_status()
            
            # Organize into clean structure
            broker_state = {
                "positions": {},
                "orders": {},
                "account": {
                    "buying_power": float(account.get('buying_power', 0)),
                    "portfolio_value": float(account.get('portfolio_value', 0)),
                    "cash": float(account.get('cash', 0))
                },
                "timestamp": datetime.now().isoformat()
            }
            
            # Process positions
            for pos in positions:
                symbol = pos['symbol']
                broker_state["positions"][symbol] = {
                    "symbol": symbol,
                    "quantity": int(pos['qty']),
                    "entry_price": float(pos['avg_entry_price']),
                    "current_price": float(pos['market_value']) / abs(int(pos['qty'])),
                    "unrealized_pl": float(pos['unrealized_pl']),
                    "side": pos['side']  # long/short
                }
            
            # Process orders (group by symbol)
            for order in orders:
                symbol = order['symbol']
                if symbol not in broker_state["orders"]:
                    broker_state["orders"][symbol] = []
                
                broker_state["orders"][symbol].append({
                    "id": order['id'],
                    "type": order['order_type'],
                    "side": order['side'],
                    "quantity": int(order['qty']),
                    "limit_price": float(order.get('limit_price', 0)) if order.get('limit_price') else None,
                    "stop_price": float(order.get('stop_price', 0)) if order.get('stop_price') else None,
                    "status": order['status'],
                    "time_in_force": order['time_in_force']
                })
            
            logger.info(f"Fetched broker state: {len(broker_state['positions'])} positions, "
                       f"{len(broker_state['orders'])} order groups")
            
            return broker_state
            
        except Exception as e:
            logger.error(f"Failed to fetch broker state: {e}")
            raise
    
    def reconcile_state(self, broker_state: Dict[str, Any]) -> List[Discrepancy]:
        """
        Reconcile local JSON with broker reality.
        JSON is for humans, broker is truth.
        """
        discrepancies = []
        
        # Check for unknown positions (at broker but not in local JSON)
        for symbol, broker_pos in broker_state["positions"].items():
            if symbol not in self.local_state["positions"]:
                discrepancies.append(Discrepancy(
                    type="UNKNOWN_POSITION",
                    symbol=symbol,
                    details={
                        "broker_quantity": broker_pos["quantity"],
                        "broker_entry": broker_pos["entry_price"],
                        "current_price": broker_pos["current_price"]
                    },
                    action="NEEDS_HUMAN_REVIEW",
                    severity="HIGH"
                ))
                
                # Auto-add to local state for tracking
                self.local_state["positions"][symbol] = {
                    "entry_price": broker_pos["entry_price"],
                    "quantity": broker_pos["quantity"],
                    "entry_time": datetime.now().isoformat(),
                    "source": "AUTO_DISCOVERED",
                    "stop_price": None,
                    "target_price": None
                }
        
        # Check for ghost positions (in local JSON but not at broker)
        for symbol in list(self.local_state["positions"].keys()):
            if symbol not in broker_state["positions"]:
                local_pos = self.local_state["positions"][symbol]
                discrepancies.append(Discrepancy(
                    type="GHOST_POSITION", 
                    symbol=symbol,
                    details={
                        "local_quantity": local_pos.get("quantity", 0),
                        "local_entry": local_pos.get("entry_price", 0)
                    },
                    action="REMOVED_FROM_JSON",
                    severity="MEDIUM"
                ))
                
                # Remove ghost position
                del self.local_state["positions"][symbol]
        
        # Check quantity mismatches
        for symbol in broker_state["positions"]:
            if symbol in self.local_state["positions"]:
                broker_qty = broker_state["positions"][symbol]["quantity"]
                local_qty = self.local_state["positions"][symbol].get("quantity", 0)
                
                if broker_qty != local_qty:
                    discrepancies.append(Discrepancy(
                        type="QUANTITY_MISMATCH",
                        symbol=symbol,
                        details={
                            "broker_quantity": broker_qty,
                            "local_quantity": local_qty,
                            "difference": broker_qty - local_qty
                        },
                        action="AUTO_FIXED",
                        severity="LOW"
                    ))
                    
                    # Fix quantity
                    self.local_state["positions"][symbol]["quantity"] = broker_qty
        
        logger.info(f"Reconciliation found {len(discrepancies)} discrepancies")
        return discrepancies
    
    def calculate_stop_adjustments(self, broker_state: Dict[str, Any]) -> List[StopAdjustment]:
        """
        Calculate which stops need adjustment based on current prices.
        Uses the same progressive stop logic from trade_lifecycle.py
        """
        adjustments = []
        
        for symbol, broker_pos in broker_state["positions"].items():
            if symbol not in self.local_state["positions"]:
                continue  # Skip unknown positions
            
            local_pos = self.local_state["positions"][symbol]
            entry_price = float(local_pos.get("entry_price", 0))
            current_price = broker_pos["current_price"]
            current_stop = local_pos.get("stop_price")
            
            if not entry_price or not current_stop:
                continue  # No entry price or stop to adjust
            
            # Calculate profit percentage
            profit_percent = (current_price - entry_price) / entry_price
            
            # Progressive stop adjustment logic with enhanced logging
            new_stop = None
            reason = ""

            if profit_percent < 0.02:  # Under 2% profit
                # Don't adjust stop - position too early
                logger.debug(f"{symbol}: No stop adjustment - profit {profit_percent:.1%} < 2% threshold")
                continue
            elif profit_percent < 0.04:  # 2-4% profit
                new_stop = entry_price  # Move to breakeven
                reason = f"Move to breakeven ({profit_percent:.1%} profit)"
                logger.info(f"{symbol}: Stop adjustment recommended - {reason}")
            elif profit_percent < 0.06:  # 4-6% profit
                new_stop = entry_price + (current_price - entry_price) * 0.25  # Lock 25%
                reason = f"Lock 25% gains ({profit_percent:.1%} profit)"
                logger.info(f"{symbol}: Stop adjustment recommended - {reason}")
            else:  # Over 6% profit
                new_stop = entry_price + (current_price - entry_price) * 0.50  # Trail 50%
                reason = f"Trail 50% gains ({profit_percent:.1%} profit)"
                logger.info(f"{symbol}: Stop adjustment recommended - {reason}")
            
            # Only adjust if new stop is higher than current stop
            if new_stop and new_stop > current_stop + 0.01:  # $0.01 minimum move
                # Find the stop order ID from broker orders
                stop_order_id = None
                if symbol in broker_state["orders"]:
                    for order in broker_state["orders"][symbol]:
                        if order["type"] in ["stop", "stop_loss"] and order["side"] == "sell":
                            stop_order_id = order["id"]
                            logger.debug(f"{symbol}: Found stop order ID {stop_order_id}")
                            break

                if stop_order_id:
                    adjustment_amount = new_stop - current_stop
                    adjustment_pct = (adjustment_amount / current_stop) * 100
                    logger.info(f"{symbol}: Creating stop adjustment - "
                               f"${current_stop:.2f} → ${new_stop:.2f} "
                               f"(+${adjustment_amount:.2f}, +{adjustment_pct:.1f}%)")

                    adjustments.append(StopAdjustment(
                        symbol=symbol,
                        order_id=stop_order_id,
                        current_stop=current_stop,
                        new_stop=new_stop,
                        reason=reason,
                        profit_percent=profit_percent
                    ))

                    # Update local state
                    self.local_state["positions"][symbol]["stop_price"] = new_stop
                else:
                    logger.warning(f"{symbol}: Stop adjustment needed but no stop order found in broker orders")
            elif new_stop:
                logger.debug(f"{symbol}: New stop ${new_stop:.2f} not significantly higher than current ${current_stop:.2f}")
        
        logger.info(f"Found {len(adjustments)} stop adjustments needed")
        return adjustments

    def check_position_alerts(self, broker_state: Dict[str, Any]) -> List[PositionAlertSummary]:
        """
        Check all positions for exit alerts (approaching TP/SL).

        Args:
            broker_state: Current broker state with positions

        Returns:
            List of position alerts
        """
        alerts = []

        for symbol, broker_pos in broker_state["positions"].items():
            if symbol not in self.local_state["positions"]:
                continue  # Skip unknown positions

            local_pos = self.local_state["positions"][symbol]
            entry_price = float(local_pos.get("entry_price", 0))
            current_price = broker_pos["current_price"]
            take_profit_price = local_pos.get("target_price")
            stop_loss_price = local_pos.get("stop_price")

            if not entry_price or not take_profit_price or not stop_loss_price:
                continue  # Skip positions without complete data

            # Create or update position in tracker
            position_id = f"{symbol}_{entry_price}"
            if position_id not in self.position_tracker.positions:
                # Create position for tracking
                self.position_tracker.create_position(
                    ticker=symbol,
                    entry_price=entry_price,
                    quantity=broker_pos["quantity"]
                )
                # Manually set TP/SL prices to match configured values
                position = self.position_tracker.positions[position_id]
                position.take_profit_price = take_profit_price
                position.stop_loss_price = stop_loss_price

            # Check for exit conditions/alerts
            exit_check = self.position_tracker.check_exit_conditions(position_id, current_price)

            if exit_check and exit_check.get('recommendation') == 'ALERT':
                # Get the most recent alert for this position
                position = self.position_tracker.positions[position_id]
                if position.alert_history:
                    recent_alert = position.alert_history[-1]
                    alerts.append(PositionAlertSummary(
                        symbol=symbol,
                        alert_type=recent_alert.alert_type.value,
                        severity=recent_alert.severity,
                        message=recent_alert.format_message(),
                        timestamp=recent_alert.timestamp.isoformat(),
                        current_price=current_price,
                        details=recent_alert.details
                    ))

        logger.info(f"Found {len(alerts)} position alerts")
        return alerts
    
    def batch_modify_orders(self, adjustments: List[StopAdjustment]) -> Dict[str, Any]:
        """
        Batch modify stop orders with enhanced logging.
        """
        if not adjustments:
            logger.info("No stop adjustments to execute")
            return {"success": True, "modifications": 0, "errors": []}

        logger.info(f"Executing {len(adjustments)} stop order modifications...")

        results = {
            "success": True,
            "modifications": 0,
            "errors": [],
            "details": []
        }

        for i, adjustment in enumerate(adjustments, 1):
            try:
                logger.info(f"[{i}/{len(adjustments)}] Modifying {adjustment.symbol} stop order...")
                logger.debug(f"  Order ID: {adjustment.order_id}")
                logger.debug(f"  Current stop: ${adjustment.current_stop:.2f}")
                logger.debug(f"  New stop: ${adjustment.new_stop:.2f}")
                logger.debug(f"  Reason: {adjustment.reason}")

                # Modify the stop order
                success = self.order_manager.modify_order(
                    order_id=adjustment.order_id,
                    stop_price=adjustment.new_stop
                )

                if success:
                    results["modifications"] += 1
                    profit_locked = adjustment.new_stop - float(self.local_state["positions"][adjustment.symbol].get("entry_price", 0))
                    detail_msg = (f"✅ {adjustment.symbol}: Stop adjusted to ${adjustment.new_stop:.2f} "
                                 f"(locking ${profit_locked:+.2f} profit)")
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

        summary = (f"Stop adjustment batch complete: {results['modifications']}/{len(adjustments)} successful, "
                  f"{len(results['errors'])} errors")
        logger.info(summary)

        return results
    
    def generate_position_summaries(self, broker_state: Dict[str, Any], 
                                    adjustments: List[StopAdjustment]) -> List[PositionSummary]:
        """Generate position summaries for reporting"""
        summaries = []
        
        # Create adjustment lookup
        adjustment_map = {adj.symbol: adj for adj in adjustments}
        
        for symbol, broker_pos in broker_state["positions"].items():
            if symbol not in self.local_state["positions"]:
                continue
            
            local_pos = self.local_state["positions"][symbol]
            current_price = broker_pos["current_price"]
            entry_price = float(local_pos.get("entry_price", 0))
            quantity = broker_pos["quantity"]
            
            # Calculate P&L
            unrealized_pl = (current_price - entry_price) * quantity
            unrealized_percent = ((current_price - entry_price) / entry_price) if entry_price else 0
            
            # Determine stop action
            stop_action = "No change"
            if symbol in adjustment_map:
                stop_action = adjustment_map[symbol].reason
            
            summaries.append(PositionSummary(
                symbol=symbol,
                entry_price=entry_price,
                current_price=current_price,
                stop_price=local_pos.get("stop_price", 0),
                target_price=local_pos.get("target_price", 0),
                quantity=quantity,
                unrealized_pl=unrealized_pl,
                unrealized_percent=unrealized_percent,
                stop_action=stop_action
            ))
        
        return summaries
    
    def generate_routine_report(self, routine_type: RoutineType,
                                broker_state: Dict[str, Any],
                                discrepancies: List[Discrepancy],
                                adjustments: List[StopAdjustment],
                                alerts: List[PositionAlertSummary] = None,
                                modification_results: Dict[str, Any] = None) -> str:
        """Generate human-readable trading report with alerts"""

        now = datetime.now()
        report_lines = [
            f"# {routine_type.value.title()} Trading Report - {now.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        # Account summary
        account = broker_state.get("account", {})
        report_lines.extend([
            "## Account Summary",
            f"Portfolio Value: ${account.get('portfolio_value', 0):,.2f}",
            f"Available Cash: ${account.get('cash', 0):,.2f}",
            f"Buying Power: ${account.get('buying_power', 0):,.2f}",
            ""
        ])
        
        # Position summaries
        summaries = self.generate_position_summaries(broker_state, adjustments)
        if summaries:
            report_lines.extend([
                "## Active Positions",
                "| Symbol | Entry | Current | Stop | Target | P&L | Action |",
                "|--------|-------|---------|------|--------|-----|--------|"
            ])
            
            for summary in summaries:
                pl_sign = "+" if summary.unrealized_pl >= 0 else ""
                report_lines.append(
                    f"| {summary.symbol} | ${summary.entry_price:.2f} | ${summary.current_price:.2f} | "
                    f"${summary.stop_price:.2f} | ${summary.target_price:.2f} | "
                    f"{pl_sign}${summary.unrealized_pl:.0f} ({summary.unrealized_percent:.1%}) | {summary.stop_action} |"
                )
            report_lines.append("")
        else:
            report_lines.extend(["## Active Positions", "No active positions", ""])
        
        # Discrepancies
        if discrepancies:
            report_lines.extend(["## Discrepancies Found"])
            for disc in discrepancies:
                severity_emoji = {"HIGH": "🚨", "MEDIUM": "⚠️", "LOW": "ℹ️"}[disc.severity]
                report_lines.append(f"{severity_emoji} {disc.type}: {disc.symbol}")
                
                if disc.type == "UNKNOWN_POSITION":
                    qty = disc.details["broker_quantity"]
                    entry = disc.details["broker_entry"]
                    report_lines.append(f"   {qty} shares at ${entry:.2f} - {disc.action}")
                elif disc.type == "GHOST_POSITION":
                    qty = disc.details["local_quantity"] 
                    report_lines.append(f"   Phantom {qty} shares - {disc.action}")
                elif disc.type == "QUANTITY_MISMATCH":
                    broker_qty = disc.details["broker_quantity"]
                    local_qty = disc.details["local_quantity"]
                    report_lines.append(f"   Broker: {broker_qty}, Local: {local_qty} - {disc.action}")
                
                report_lines.append("")

        # Position Alerts
        if alerts:
            report_lines.extend(["## Position Alerts"])
            # Count by severity
            critical_count = len([a for a in alerts if a.severity == "CRITICAL"])
            warning_count = len([a for a in alerts if a.severity == "WARNING"])
            info_count = len([a for a in alerts if a.severity == "INFO"])

            report_lines.append(f"Total Alerts: {len(alerts)} (🚨 {critical_count} Critical, ⚠️ {warning_count} Warning, 📊 {info_count} Info)")
            report_lines.append("")

            for alert in alerts:
                report_lines.append(alert.message)

            report_lines.append("")

        # Stop modifications
        if modification_results:
            report_lines.extend(["## Stop Adjustments"])
            if modification_results["modifications"] > 0:
                report_lines.append(f"✅ {modification_results['modifications']} stops adjusted successfully")
            
            if modification_results["errors"]:
                report_lines.append("❌ Errors:")
                for error in modification_results["errors"]:
                    report_lines.append(f"   {error}")
            report_lines.append("")
        
        # Footer
        next_routine = "evening" if routine_type == RoutineType.MORNING else "morning"
        next_time = "15:50:00" if routine_type == RoutineType.MORNING else "09:20:00"
        report_lines.extend([
            "---",
            f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Next {next_routine} routine: {next_time}",
            f"Cost: ~3-5 API calls total"
        ])
        
        return "\n".join(report_lines)
    
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

            # Step 4: Calculate stop adjustments needed (no API calls)
            adjustments = self.calculate_stop_adjustments(broker_state)

            # Step 5: Batch modify stops if needed (single API call)
            modification_results = None
            if adjustments:
                modification_results = self.batch_modify_orders(adjustments)

            # Step 6: Save updated local state
            self.local_state["discrepancies"] = [asdict(d) for d in discrepancies]
            self.save_local_state()

            # Step 7: Generate human report with alerts
            report = self.generate_routine_report(
                RoutineType.MORNING, broker_state, discrepancies,
                adjustments, alerts, modification_results
            )
            
            # Save report to file
            report_file = f"reports/daily/{datetime.now().strftime('%Y%m%d_%H%M')}_morning.md"
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, 'w') as f:
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

            # Evening-specific: Check for positions that might need closing
            # (This is where we might add EOD logic later)

            self.save_local_state()

            report = self.generate_routine_report(
                RoutineType.EVENING, broker_state, discrepancies, [], alerts
            )
            
            report_file = f"reports/daily/{datetime.now().strftime('%Y%m%d_%H%M')}_evening.md"
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, 'w') as f:
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
            
            # Rebuild local state from broker truth
            self.local_state = {
                "positions": {},
                "last_update": datetime.now().isoformat(),
                "discrepancies": [],
                "recovery_timestamp": datetime.now().isoformat()
            }
            
            # Auto-discover all positions
            for symbol, broker_pos in broker_state["positions"].items():
                self.local_state["positions"][symbol] = {
                    "entry_price": broker_pos["entry_price"],
                    "quantity": broker_pos["quantity"],
                    "entry_time": "UNKNOWN",
                    "source": "CRASH_RECOVERY",
                    "stop_price": None,  # Will need human input
                    "target_price": None  # Will need human input
                }
            
            self.save_local_state()
            
            # Generate recovery report
            recovery_lines = [
                f"# Crash Recovery Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                f"Recovered {len(broker_state['positions'])} positions",
                f"Recovered {len(broker_state['orders'])} order groups",
                "",
                "## Recovered Positions",
            ]
            
            for symbol, pos in self.local_state["positions"].items():
                recovery_lines.append(f"- {symbol}: {pos['quantity']} shares @ ${pos['entry_price']:.2f}")
            
            recovery_lines.extend([
                "",
                "⚠️ **MANUAL ACTION REQUIRED:**",
                "- Review all positions for accuracy",  
                "- Set stop_price and target_price for each position",
                "- Verify entry times if needed for tax reporting",
                ""
            ])
            
            report = "\n".join(recovery_lines)
            
            # Save recovery report
            report_file = f"reports/daily/{datetime.now().strftime('%Y%m%d_%H%M')}_recovery.md"
            os.makedirs(os.path.dirname(report_file), exist_ok=True)
            with open(report_file, 'w') as f:
                f.write(report)
            
            logger.info(f"Crash recovery complete. Report saved to {report_file}")
            return report
            
        except Exception as e:
            error_msg = f"Crash recovery failed: {e}"
            logger.error(error_msg)
            return f"❌ {error_msg}"


def main():
    """Demo the cost-efficient trade cycle"""
    print("=== Cost-Efficient Trade Cycle Demo ===")
    
    try:
        cycle = CostEfficientTradeCycle()
        
        print("\n1. Running morning routine...")
        morning_report = cycle.morning_routine()
        print(morning_report)
        
        print("\n" + "="*50)
        print("Morning routine complete!")
        print("Next: Run evening routine at 3:50 PM ET")
        
    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()