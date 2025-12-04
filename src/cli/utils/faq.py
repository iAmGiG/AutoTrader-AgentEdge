"""
FAQ Module - Load and display FAQ with features, how-to, and resources.

Replaces trading_tips.py with expandable section-based structure.
"""

import logging
import os
from typing import Dict, List, Optional

import yaml

from src.utils.safe_print import safe_print

logger = logging.getLogger(__name__)

# Cache for loaded FAQ
_faq_cache: Optional[Dict] = None


def _get_faq_path() -> str:
    """Get path to faq.yaml config file."""
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    return os.path.join(project_root, "config_defaults", "faq.yaml")


def load_faq() -> Dict:
    """
    Load FAQ from YAML config.

    Returns:
        Dict with FAQ configuration, or default structure if load fails
    """
    global _faq_cache

    if _faq_cache is not None:
        return _faq_cache

    try:
        config_path = os.path.normpath(_get_faq_path())

        if not os.path.exists(config_path):
            logger.warning(f"FAQ config not found: {config_path}")
            return _get_default_faq()

        with open(config_path, "r", encoding="utf-8") as f:
            _faq_cache = yaml.safe_load(f)
            logger.debug("Loaded FAQ from config")
            return _faq_cache

    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Failed to load FAQ: {e}")
        return _get_default_faq()


def _get_default_faq() -> Dict:
    """Return default FAQ structure if config loading fails."""
    return {
        "header": {"title": "FAQ & GUIDE", "separator_char": "=", "separator_width": 60},
        "sections": [
            {
                "id": "features",
                "title": "FEATURES",
                "emoji": "~",
                "items": [
                    {"title": "Entry Timing", "content": "Use 'buy at pullback' for better prices"}
                ],
            }
        ],
        "quick_ref": {
            "title": "QUICK REFERENCE",
            "emoji": ">",
            "items": ["Type /help for commands"],
        },
    }


def show_faq(section_filter: Optional[str] = None) -> str:
    """
    Format and return FAQ for display.

    Args:
        section_filter: Optional section ID to show only that section
                       ('features', 'how', 'resources')

    Returns:
        Formatted string with FAQ content
    """
    faq = load_faq()
    header = faq.get("header", {})
    lines: List[str] = []

    sep_char = header.get("separator_char", "=")
    sep_width = header.get("separator_width", 60)
    separator = sep_char * sep_width
    thin_sep = "-" * sep_width

    # Header
    lines.append("")
    lines.append(separator)
    lines.append(f"  {header.get('title', 'FAQ & GUIDE')}")
    lines.append(separator)

    # Sections
    for section in faq.get("sections", []):
        section_id = section.get("id", "")

        # Filter if requested
        if section_filter and section_id != section_filter:
            continue

        emoji = section.get("emoji", "*")
        title = section.get("title", "")

        lines.append(f"\n[{emoji}] {title}")
        lines.append(thin_sep)

        for item in section.get("items", []):
            item_title = item.get("title", "")
            content = item.get("content", "").strip()
            link = item.get("link", "")

            if item_title:
                lines.append(f"  {item_title}")
            if content:
                # Indent content lines
                for line in content.split("\n"):
                    lines.append(f"    {line}")
            if link:
                lines.append(f"    -> {link}")
            lines.append("")

    # Quick reference (only show if no filter)
    if not section_filter:
        quick = faq.get("quick_ref", {})
        if quick:
            lines.append(f"[{quick.get('emoji', '>')}] {quick.get('title', 'QUICK REFERENCE')}")
            lines.append(thin_sep)
            for item in quick.get("items", []):
                lines.append(f"  {item}")

    lines.append("")
    lines.append(separator)

    return "\n".join(lines)


def display_faq(section_filter: Optional[str] = None) -> None:
    """Display FAQ using safe_print."""
    output = show_faq(section_filter)
    safe_print(output)


def get_available_sections() -> List[str]:
    """Get list of available section IDs."""
    faq = load_faq()
    return [s.get("id", "") for s in faq.get("sections", []) if s.get("id")]


__all__ = [
    "load_faq",
    "show_faq",
    "display_faq",
    "get_available_sections",
]
