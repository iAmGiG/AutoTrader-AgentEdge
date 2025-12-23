"""
CLI Voter Commands (Issue #488)

Natural language commands for managing ranked voting configuration.
Exposes RankedVoterManager functionality to the CLI.

Commands:
    /voter list              - Show active/review voters with rankings
    /voter preset <name>     - Switch preset (default, macd_primary, rsi_primary)
    /voter promote <name>    - Promote voter to active tier
    /voter demote <name>     - Demote voter to review tier
    /voter info              - Show current voting configuration
"""

from src.core.ranked_voter_config import get_ranked_voter_manager


class VoterCommands:
    """CLI commands for voter ranking management."""

    _instance = None
    _initialized: bool = False

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super(VoterCommands, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize voter commands."""
        if self._initialized:
            return
        self.manager = get_ranked_voter_manager()
        self._initialized = True

    def list_voters(self, verbose: bool = False) -> str:
        """
        List all voters with their rankings.

        Args:
            verbose: Show detailed parameters

        Returns:
            Formatted output string
        """
        active = self.manager.get_active_voters()
        review = self.manager.get_review_voters()

        output = "🗳️ Voter Rankings\n"
        output += "=" * 50 + "\n\n"

        # Active voters
        output += "Active Voters (participate in decisions):\n"
        output += "-" * 50 + "\n"
        if active:
            for voter in active:
                output += f"  #{voter.rank} {voter.name}"
                if verbose and voter.params:
                    params_str = ", ".join(f"{k}={v}" for k, v in voter.params.items())
                    output += f" ({params_str})"
                output += "\n"
        else:
            output += "  (none)\n"

        output += "\n"

        # Review voters
        output += "Review Voters (shown but don't vote):\n"
        output += "-" * 50 + "\n"
        if review:
            for voter in review:
                output += f"  #{voter.rank} {voter.name}"
                if verbose and voter.params:
                    params_str = ", ".join(f"{k}={v}" for k, v in voter.params.items())
                    output += f" ({params_str})"
                output += "\n"
        else:
            output += "  (none)\n"

        # Summary
        output += "\n" + "-" * 50 + "\n"
        output += f"Total: {len(active)} active, {len(review)} review\n"

        return output

    def show_info(self) -> str:
        """
        Show current voting configuration.

        Returns:
            Formatted output string
        """
        voting_config = self.manager.get_voting_config()
        active_count = self.manager.get_active_voter_count()

        output = "📊 Voting Configuration\n"
        output += "=" * 50 + "\n\n"

        output += "Consensus Settings:\n"
        output += "-" * 50 + "\n"
        output += f"  Mode:            {voting_config.consensus_mode}\n"
        output += f"  Active Voters:   {active_count}\n"
        output += f"  Min Data Points: {voting_config.min_data_points}\n"
        output += "\n"

        output += "Confidence Adjustments:\n"
        output += "-" * 50 + "\n"
        output += f"  Consensus Boost:   +{voting_config.consensus_boost:.0%}\n"
        output += f"  Weak Signal Boost: +{voting_config.weak_signal_boost:.0%}\n"
        output += f"  Conflict Penalty:  -{voting_config.conflict_penalty:.0%}\n"
        output += "\n"

        output += "Position Sizing:\n"
        output += "-" * 50 + "\n"
        output += f"  Strong Signal: {voting_config.strong_signal_size:.0%} position\n"
        output += f"  Weak Signal:   {voting_config.weak_signal_size:.0%} position\n"
        output += f"  Conflict:      {voting_config.conflict_size:.0%} position\n"

        return output

    def list_presets(self) -> str:
        """
        List available presets.

        Returns:
            Formatted output string
        """
        presets = self.manager.get_available_presets()

        output = "📋 Available Presets\n"
        output += "=" * 50 + "\n"

        for name, description in presets.items():
            output += f"  {name}: {description}\n"

        output += "\n" + "-" * 50 + "\n"
        output += "Usage: /voter preset <name>\n"

        return output

    def apply_preset(self, preset_name: str) -> str:
        """
        Apply a preset configuration.

        Args:
            preset_name: Name of the preset

        Returns:
            Status message
        """
        success = self.manager.apply_preset(preset_name)

        if success:
            return f"✅ Applied preset '{preset_name}'"

        presets = list(self.manager.get_available_presets().keys())
        return f"❌ Preset '{preset_name}' not found. Available: {', '.join(presets)}"

    def promote_voter(self, name: str) -> str:
        """
        Promote a voter one rank higher.

        Args:
            name: Voter name (e.g., 'MACD', 'RSI')

        Returns:
            Status message
        """
        name = name.upper()
        success = self.manager.promote_voter(name)

        if success:
            ranking = self.manager.get_ranking()
            voter = next((v for v in ranking if v.name == name), None)
            new_rank = voter.rank if voter else "?"
            return f"✅ Promoted {name} to rank #{new_rank}"

        # Check if voter exists
        ranking = self.manager.get_ranking()
        voter = next((v for v in ranking if v.name == name), None)
        if voter is None:
            available = [v.name for v in ranking]
            return f"❌ Voter '{name}' not found. Available: {', '.join(available)}"

        return f"❌ {name} is already at the top rank"

    def demote_voter(self, name: str) -> str:
        """
        Demote a voter one rank lower.

        Args:
            name: Voter name (e.g., 'MACD', 'RSI')

        Returns:
            Status message
        """
        name = name.upper()
        success = self.manager.demote_voter(name)

        if success:
            ranking = self.manager.get_ranking()
            voter = next((v for v in ranking if v.name == name), None)
            new_rank = voter.rank if voter else "?"
            return f"✅ Demoted {name} to rank #{new_rank}"

        ranking = self.manager.get_ranking()
        voter = next((v for v in ranking if v.name == name), None)
        if voter is None:
            available = [v.name for v in ranking]
            return f"❌ Voter '{name}' not found. Available: {', '.join(available)}"

        return f"❌ {name} is already at the bottom rank"

    def set_voter_role(self, name: str, role: str) -> str:
        """
        Change a voter's role.

        Args:
            name: Voter name
            role: New role ('active' or 'review')

        Returns:
            Status message
        """
        name = name.upper()
        role = role.lower()

        if role not in ("active", "review"):
            return f"❌ Invalid role '{role}'. Use 'active' or 'review'"

        success = self.manager.set_voter_role(name, role)

        if success:
            return f"✅ Set {name} to {role} role"

        ranking = self.manager.get_ranking()
        available = [v.name for v in ranking]
        return f"❌ Voter '{name}' not found. Available: {', '.join(available)}"


# Singleton accessor
def get_voter_commands() -> VoterCommands:
    """Get the VoterCommands singleton instance."""
    return VoterCommands()
