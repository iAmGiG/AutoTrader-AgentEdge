"""
Slash Command Handlers - CLI commands starting with /.

Issue #468: Self-registering commands using CommandRegistry.

All slash commands are registered here and auto-discovered
when this module is imported.
"""

import logging

from src.cli.commands.registry import command
from src.utils.safe_print import safe_print

logger = logging.getLogger(__name__)


# =============================================================================
# EXIT COMMANDS
# =============================================================================


@command("/exit", aliases=["/quit"], help_text="Exit the CLI")
def cmd_exit(session) -> bool:
    """Exit the CLI session."""
    return False  # Signal to exit


# =============================================================================
# HELP COMMAND
# =============================================================================


@command("/help", help_text="Show help", has_args=True)
def cmd_help(session, args: str = None):
    """Show help information."""
    if args:
        # Delegate to help system for topic-specific help
        help_output = session.help_system.handle_help_command(f"/help {args}")
    else:
        help_output = session.help_system.handle_help_command("/help")
    safe_print(help_output)


# =============================================================================
# MODE TOGGLE
# =============================================================================


@command("/toggle", help_text="Switch CONFIRM/AUTO mode")
def cmd_toggle(session):
    """Toggle between confirm and auto execution modes."""
    from config_defaults.cli_messages import CLIMessages as MSG  # noqa: N814

    if session.autonomy_mode == "confirm":
        session.autonomy_mode = "auto"
        print(MSG.MODE_SWITCHED_AUTO)
    else:
        session.autonomy_mode = "confirm"
        print(MSG.MODE_SWITCHED_CONFIRM)


# =============================================================================
# SCHEDULER
# =============================================================================


@command("/schedule", help_text="Scheduler management")
async def cmd_schedule(session):
    """Enter scheduler management mode."""
    from src.cli.scheduler_cli import SchedulerCLI

    scheduler_cli = SchedulerCLI(session.scheduler)
    await scheduler_cli.run()


# =============================================================================
# FAQ (replaces /tips)
# =============================================================================


@command("/faq", aliases=["/guide"], help_text="Features & how-to guide", has_args=True)
def cmd_faq(session, args: str = None):
    """Show FAQ with optional section filter."""
    from src.cli.utils.faq import display_faq, get_available_sections

    section = args.strip().lower() if args else None

    if section and section not in get_available_sections():
        safe_print(f"Unknown section: {section}")
        safe_print(f"Available: {', '.join(get_available_sections())}")
        return

    display_faq(section)


@command("/tips", help_text="(moved to /faq)")
def cmd_tips_legacy(session):
    """Legacy /tips - redirect to /faq."""
    safe_print("Tip: /tips has moved to /faq")
    from src.cli.utils.faq import display_faq

    display_faq()


# =============================================================================
# ABOUT / STATUS
# =============================================================================


@command("/about", aliases=["/status"], help_text="Status dashboard")
def cmd_about(session):
    """Show status dashboard."""
    from src.cli.utils.about_page import display_about

    display_about(session.account_monitor)


# =============================================================================
# CLEAR / HOME
# =============================================================================


@command("/clear", aliases=["/home", "/cls"], help_text="Clear screen, show home")
def cmd_clear(session):
    """Clear screen and show welcome/home page."""
    import os
    import platform

    # Clear screen (cross-platform)
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

    # Show welcome page
    session._print_welcome()


# =============================================================================
# MODE - Trading risk mode
# =============================================================================


@command("/mode", help_text="Show/set trading mode", has_args=True)
def cmd_mode(session, args: str = None):
    """Show or set trading risk mode (conservative/moderate/aggressive)."""
    from src.cli.tools.mode_tools import set_mode, show_current_mode

    if args:
        # Set mode
        mode_arg = args.strip().lower()
        result = set_mode(mode_arg)
        safe_print(result)
    else:
        # Show current mode
        result = show_current_mode()
        safe_print(result)


# =============================================================================
# VOTER - Ranked voting management (#488)
# =============================================================================


def _voter_handle_subcommand(vc, subcommand: str, subarg: str | None) -> str:
    """Handle voter subcommands. Returns output string."""
    if subcommand in ("list", "ls"):
        return vc.list_voters(verbose=bool(subarg))
    if subcommand == "info":
        return vc.show_info()
    if subcommand == "presets":
        return vc.list_presets()
    if subcommand == "preset":
        if not subarg:
            return f"Usage: /voter preset <name>\n{vc.list_presets()}"
        return vc.apply_preset(subarg)
    if subcommand == "promote":
        return vc.promote_voter(subarg) if subarg else "Usage: /voter promote <name>"
    if subcommand == "demote":
        return vc.demote_voter(subarg) if subarg else "Usage: /voter demote <name>"
    if subcommand in ("role", "set-role"):
        if not subarg or " " not in subarg:
            return "Usage: /voter role <name> <active|review>"
        name, role = subarg.split(maxsplit=1)
        return vc.set_voter_role(name, role)
    return f"Unknown subcommand: {subcommand}\nUse /voter for help"


@command("/voter", help_text="Ranked voter management", has_args=True)
def cmd_voter(session, args: str = None):
    """
    Manage ranked voters for trading decisions.

    Usage:
        /voter              Show voter rankings
        /voter list         Show active/review voters
        /voter info         Show voting configuration
        /voter presets      List available presets
        /voter preset NAME  Apply a preset (default, macd_primary, rsi_primary)
        /voter promote NAME Promote voter one rank
        /voter demote NAME  Demote voter one rank
    """
    from src.cli.commands.voter_commands import get_voter_commands

    vc = get_voter_commands()

    if not args:
        safe_print(vc.list_voters())
        return

    parts = args.strip().split(maxsplit=1)
    subcommand = parts[0].lower()
    subarg = parts[1] if len(parts) > 1 else None

    safe_print(_voter_handle_subcommand(vc, subcommand, subarg))


# =============================================================================
# Ensure commands are registered on import
# =============================================================================

logger.debug(
    f"Slash commands registered: {len(__import__('src.cli.commands.registry', fromlist=['CommandRegistry']).CommandRegistry.list_commands())}"
)
