"""
GTT (Good-Till-Triggered) Module - Persistent price triggers.

Issue #340: Implement GTT-style persistent triggers that stay active across sessions.

This module provides:
- Persistent price triggers (days/weeks)
- Repeating or one-time triggers
- Alert and order placement actions
- OCO (One-Cancels-Other) trigger groups
- Multi-day trailing stops

Components:
- gtt_manager.py: CRUD operations and persistence
- trigger_evaluator.py: Condition checking logic
- action_executor.py: Execute trigger actions
"""

from src.trading.gtt.gtt_manager import (
                                         ActionType,
                                         ConditionType,
                                         GTTManager,
                                         GTTTrigger,
                                         get_gtt_manager,
)

__all__ = [
    "GTTManager",
    "GTTTrigger",
    "ConditionType",
    "ActionType",
    "get_gtt_manager",
]
