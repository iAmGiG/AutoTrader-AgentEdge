"""
Trading Tips Module - Load and display educational trading tips.

Issue #436: Extracted from cli_session.py for configurability.

Tips are loaded from config_defaults/trading_tips.yaml to allow
easy customization without code changes.
"""

import logging
import os
from typing import Dict, Optional

import yaml

from src.utils.safe_print import safe_print

logger = logging.getLogger(__name__)

# Cache for loaded tips
_tips_cache: Optional[Dict] = None


def _get_tips_path() -> str:
    """Get path to trading_tips.yaml config file."""
    # Go up from utils/ -> cli/ -> src/ -> project root
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return os.path.join(project_root, "config_defaults", "trading_tips.yaml")


def load_trading_tips() -> Dict:
    """
    Load trading tips from YAML config.

    Returns:
        Dict with tips configuration, or default structure if load fails
    """
    global _tips_cache

    if _tips_cache is not None:
        return _tips_cache

    try:
        config_path = os.path.normpath(_get_tips_path())

        if not os.path.exists(config_path):
            logger.warning(f"Trading tips config not found: {config_path}")
            return _get_default_tips()

        with open(config_path, "r", encoding="utf-8") as f:
            _tips_cache = yaml.safe_load(f)
            logger.debug("Loaded trading tips from config")
            return _tips_cache

    except Exception as e:
        logger.warning(f"Failed to load trading tips: {e}")
        return _get_default_tips()


def _get_default_tips() -> Dict:
    """Return default tips structure if config loading fails."""
    return {
        "header": {
            "title": "TRADING BASICS FOR BEGINNERS",
            "separator_char": "=",
            "separator_width": 70,
        },
        "sections": [
            {
                "id": "buy_vs_short",
                "title": "BUY vs SHORT",
                "emoji": "1️⃣",
                "content": "BUY = Stock goes UP. SHORT = Stock goes DOWN (risky).",
            }
        ],
        "quick_tips": {
            "title": "QUICK TIPS",
            "emoji": "💡",
            "items": ["Start small", "Use CONFIRM mode"],
        },
    }


def get_tips_dict() -> Dict[str, str]:
    """
    Get tips as simple key-value dict for backward compatibility.

    Returns:
        Dict mapping tip IDs to content strings
    """
    tips = load_trading_tips()
    result = {}

    for section in tips.get("sections", []):
        tip_id = section.get("id", "")
        content = section.get("content", "")
        if tip_id and content:
            result[tip_id] = content.strip()

    return result


def show_trading_tips() -> str:
    """
    Format and return trading tips for display.

    Returns:
        Formatted string with all trading tips
    """
    tips = load_trading_tips()
    header = tips.get("header", {})
    lines = []

    # Header
    sep_char = header.get("separator_char", "=")
    sep_width = header.get("separator_width", 70)
    separator = sep_char * sep_width

    lines.append("")
    lines.append(separator)
    lines.append(f"📚 {header.get('title', 'TRADING TIPS')}")
    lines.append(separator)

    # Sections
    for section in tips.get("sections", []):
        emoji = section.get("emoji", "•")
        title = section.get("title", "")
        content = section.get("content", "").strip()

        lines.append(f"\n{emoji}  {title}")
        lines.append("-" * sep_width)
        lines.append(content)

    # Quick tips
    quick = tips.get("quick_tips", {})
    if quick:
        lines.append(f"\n{quick.get('emoji', '💡')} {quick.get('title', 'TIPS')}:")
        lines.append("-" * sep_width)
        for item in quick.get("items", []):
            lines.append(f"• {item}")

    lines.append("")
    lines.append(separator)

    return "\n".join(lines)


def display_trading_tips() -> None:
    """Display trading tips using safe_print."""
    output = show_trading_tips()
    safe_print(output)


__all__ = [
    "load_trading_tips",
    "get_tips_dict",
    "show_trading_tips",
    "display_trading_tips",
]
