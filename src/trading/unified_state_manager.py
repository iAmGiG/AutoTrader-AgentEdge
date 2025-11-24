#!/usr/bin/env python3
"""
Unified State Manager

Single source of truth for all position and trade state across the system.
Prevents state fragmentation and ensures consistency.
"""

import json
import logging
import os
import sys
from datetime import datetime  # TODO Date utils
from threading import Lock
from typing import Any, Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

logger = logging.getLogger(__name__)


class UnifiedStateManager:
    """
    Centralized state management for all trading positions and orders.

    This replaces the fragmented state files:
    - positions.json
    - llm_positions.json
    - cost_efficient_positions.json

    Now all modules use this single source of truth.
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, state_dir: str = "state", state_file: str = "unified_trading_state.json"):
        if hasattr(self, "initialized") and self.initialized:
            return

        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, state_file)

        # Ensure state directory exists
        os.makedirs(self.state_dir, exist_ok=True)

        # Load or initialize state
        self.state = self._load_state()
        self.initialized = True

        logger.info(
            f"UnifiedStateManager initialized with {len(self.state.get('positions', {}))} positions"
        )

    def _load_state(self) -> Dict[str, Any]:
        """Load state from disk or create new."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)

                # Migrate old state files if they exist
                self._migrate_legacy_states(state)
                return state

            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load state file: {e}")
                return self._create_empty_state()
        else:
            # Check for legacy state files to migrate
            state = self._create_empty_state()
            self._migrate_legacy_states(state)
            return state

    def _create_empty_state(self) -> Dict[str, Any]:
        """Create an empty state structure."""
        return {
            "positions": {},
            "orders": {},
            "trade_history": [],
            "last_update": datetime.now().isoformat(),
            "version": "2.0",
            "stats": {"total_trades": 0, "winning_trades": 0, "losing_trades": 0, "total_pnl": 0.0},
        }

    def _migrate_legacy_states(self, state: Dict[str, Any]):
        """Migrate data from old state files if they exist."""
        legacy_files = [
            "state/positions.json",
            "state/llm_positions.json",
            "state/cost_efficient_positions.json",
        ]

        migrated = False
        for legacy_file in legacy_files:
            if os.path.exists(legacy_file):
                try:
                    with open(legacy_file, "r") as f:
                        legacy_data = json.load(f)

                    # Merge positions
                    if "positions" in legacy_data:
                        for symbol, pos_data in legacy_data["positions"].items():
                            if symbol not in state["positions"]:
                                state["positions"][symbol] = pos_data
                                logger.info(f"Migrated position {symbol} from {legacy_file}")
                                migrated = True

                    # Archive the old file
                    archive_name = legacy_file + ".migrated"
                    os.rename(legacy_file, archive_name)
                    logger.info(f"Archived {legacy_file} to {archive_name}")

                except Exception as e:
                    logger.error(f"Failed to migrate {legacy_file}: {e}")

        if migrated:
            self._save_state()

    def _save_state(self):
        """Save state to disk with atomic write."""
        with self._lock:
            try:
                # Update timestamp
                self.state["last_update"] = datetime.now().isoformat()

                # Write to temp file first
                temp_file = self.state_file + ".tmp"
                with open(temp_file, "w") as f:
                    json.dump(self.state, f, indent=2, default=str)

                # Atomic rename
                os.replace(temp_file, self.state_file)

                logger.debug(f"State saved to {self.state_file}")

            except Exception as e:
                logger.error(f"Failed to save state: {e}")
                raise

    # Position management

    def add_position(self, symbol: str, data: Dict[str, Any]) -> bool:
        """Add or update a position."""
        with self._lock:
            try:
                self.state["positions"][symbol] = {
                    **data,
                    "last_update": datetime.now().isoformat(),
                }
                self._save_state()
                logger.info(f"Added/updated position: {symbol}")
                return True

            except Exception as e:
                logger.error(f"Failed to add position {symbol}: {e}")
                return False

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get a specific position."""
        return self.state["positions"].get(symbol)

    def get_all_positions(self) -> Dict[str, Any]:
        """Get all positions."""
        return self.state["positions"].copy()

    def remove_position(self, symbol: str) -> bool:
        """Remove a position."""
        with self._lock:
            if symbol in self.state["positions"]:
                # Move to history before removing
                position = self.state["positions"][symbol]
                position["closed_time"] = datetime.now().isoformat()
                self.state["trade_history"].append(position)

                # Update stats
                if "pnl" in position:
                    self.state["stats"]["total_trades"] += 1
                    self.state["stats"]["total_pnl"] += position["pnl"]
                    if position["pnl"] > 0:
                        self.state["stats"]["winning_trades"] += 1
                    else:
                        self.state["stats"]["losing_trades"] += 1

                # Remove from active positions
                del self.state["positions"][symbol]
                self._save_state()

                logger.info(f"Removed position: {symbol}")
                return True
            return False

    # Order management

    def add_order(self, order_id: str, data: Dict[str, Any]) -> bool:
        """Add or update an order."""
        with self._lock:
            try:
                self.state["orders"][order_id] = {**data, "last_update": datetime.now().isoformat()}
                self._save_state()
                logger.info(f"Added/updated order: {order_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to add order {order_id}: {e}")
                return False

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific order."""
        return self.state["orders"].get(order_id)

    def get_orders_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Get all orders for a specific symbol."""
        orders = []
        for order_id, order_data in self.state["orders"].items():
            if order_data.get("symbol") == symbol:
                orders.append({**order_data, "order_id": order_id})
        return orders

    def remove_order(self, order_id: str) -> bool:
        """Remove an order."""
        with self._lock:
            if order_id in self.state["orders"]:
                del self.state["orders"][order_id]
                self._save_state()
                logger.info(f"Removed order: {order_id}")
                return True
            return False

    # Utility methods

    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics."""
        return self.state["stats"].copy()

    def clear_all(self, confirm: bool = False):
        """Clear all state (use with caution)."""
        if confirm:
            with self._lock:
                self.state = self._create_empty_state()
                self._save_state()
                logger.warning("All state cleared!")

    def export_for_analysis(self) -> Dict[str, Any]:
        """Export complete state for analysis."""
        return {
            "positions": self.state["positions"],
            "orders": self.state["orders"],
            "history": self.state["trade_history"][-100:],  # Last 100 trades
            "stats": self.state["stats"],
            "export_time": datetime.now().isoformat(),
        }


# Singleton instance
state_manager = UnifiedStateManager()

# Convenience functions for backward compatibility


def add_position(symbol: str, data: Dict[str, Any]) -> bool:
    return state_manager.add_position(symbol, data)


def get_position(symbol: str) -> Optional[Dict[str, Any]]:
    return state_manager.get_position(symbol)


def get_all_positions() -> Dict[str, Any]:
    return state_manager.get_all_positions()


def remove_position(symbol: str) -> bool:
    return state_manager.remove_position(symbol)
