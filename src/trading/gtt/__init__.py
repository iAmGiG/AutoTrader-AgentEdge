"""
GTT (Good-Till-Triggered) Module - Persistent price triggers.

Issue #340: Implement GTT-style persistent triggers that stay active across sessions.

This module provides:
- Persistent price triggers (days/weeks)
- Repeating or one-time triggers
- Alert and order placement actions
- OCO (One-Cancels-Other) trigger groups
- Multi-day trailing stops (Phase 3)

Components:
- gtt_manager.py: CRUD operations and persistence
- trigger_evaluator.py: Condition checking logic
- action_executor.py: Execute trigger actions
- trailing_stop_bridge.py: Multi-day trailing stop persistence (Phase 3)
"""

from src.trading.gtt.gtt_manager import (
                                         ActionType,
                                         ConditionType,
                                         GTTManager,
                                         GTTTrigger,
                                         get_gtt_manager,
)
from src.trading.gtt.trailing_stop_bridge import (
                                         cleanup_orphaned_trailing_stops,
                                         get_trailing_stop_status,
                                         restore_trailing_stops_from_gtt,
                                         sync_all_trailing_stops,
                                         sync_trailing_stop_to_gtt,
)

__all__ = [
    # GTT Manager
    "GTTManager",
    "GTTTrigger",
    "ConditionType",
    "ActionType",
    "get_gtt_manager",
    # Phase 3: Trailing Stop Bridge
    "sync_trailing_stop_to_gtt",
    "restore_trailing_stops_from_gtt",
    "sync_all_trailing_stops",
    "cleanup_orphaned_trailing_stops",
    "get_trailing_stop_status",
]
