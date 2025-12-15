#!/usr/bin/env python3
"""
Ranked Voter Configuration Manager

Issue #364: Implement Ranked Voter System for Technical Indicators

Manages ranked voter configuration with:
- YAML-based indicator definitions and rankings
- SQLite persistence for user's current ranking
- Support for active vs review-only voters
- Preset configurations for different trading styles

Pattern follows TradingModeManager (Issue #400).
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

from src.utils.date_utils import now_iso

logger = logging.getLogger(__name__)


@dataclass
class VoterConfig:
    """Configuration for a single voter in the ranking."""

    name: str
    rank: int
    role: str  # "active" or "review"
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "rank": self.rank,
            "role": self.role,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoterConfig":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            rank=data.get("rank", 999),
            role=data.get("role", "review"),
            params=data.get("params", {}),
        )


@dataclass
class VotingConfig:
    """Voting logic configuration."""

    consensus_mode: str = "unanimous"  # unanimous, majority, weighted
    consensus_boost: float = 0.15
    weak_signal_boost: float = 0.10
    conflict_penalty: float = 0.20
    strong_signal_size: float = 1.0
    weak_signal_size: float = 0.5
    conflict_size: float = 0.0
    min_data_points: int = 42


class RankedVoterManager:
    """
    Manages ranked voter configuration and persistence.

    Loads voter rankings from YAML config and persists user's
    current ranking to SQLite database.
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize ranked voter manager.

        Args:
            config_file: Path to voters_config.yaml (default: config_defaults/)
        """
        if yaml is None:
            raise ImportError("PyYAML required. Install with: pip install pyyaml")

        if config_file is None:
            config_dir = os.path.join(os.path.dirname(__file__), "../../config_defaults")
            config_file = os.path.join(config_dir, "voters_config.yaml")

        self.config_file = config_file
        self._config = self._load_config()

        # SQLite database for persisting current ranking
        db_dir = os.path.join(os.path.dirname(__file__), "../../state")
        os.makedirs(db_dir, exist_ok=True)
        self._db_path = os.path.join(db_dir, "user.db")
        self._init_database()

        # Load persisted ranking or use default
        self._current_ranking = self._load_persisted_ranking() or self._get_default_ranking()
        self._voting_config = self._load_voting_config()

        logger.info(
            f"RankedVoterManager initialized: {len(self._current_ranking)} voters, "
            f"{self.get_active_voter_count()} active"
        )

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_file):
            logger.warning(f"Config file not found: {self.config_file}, using defaults")
            return self._get_default_config()

        with open(self.config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            logger.debug(f"Loaded voters config from {self.config_file}")
            return config

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration if file not found."""
        return {
            "active_voters": 2,
            "indicators": {
                "MACD": {
                    "description": "Moving Average Convergence Divergence",
                    "default_params": {"fast": 13, "slow": 34, "signal": 8, "threshold": 0.1},
                    "required_periods": 42,
                    "validated": True,
                },
                "RSI": {
                    "description": "Relative Strength Index",
                    "default_params": {"period": 14, "oversold": 30, "overbought": 70},
                    "required_periods": 24,
                    "validated": True,
                },
            },
            "default_ranking": [
                {"name": "MACD", "rank": 1, "params": {}, "role": "active"},
                {"name": "RSI", "rank": 2, "params": {}, "role": "active"},
            ],
            "voting": {
                "consensus_mode": "unanimous",
                "consensus_boost": 0.15,
                "weak_signal_boost": 0.10,
                "conflict_penalty": 0.20,
                "strong_signal_size": 1.0,
                "weak_signal_size": 0.5,
                "conflict_size": 0.0,
                "min_data_points": 42,
            },
        }

    def _get_default_ranking(self) -> List[VoterConfig]:
        """Get default ranking from config."""
        ranking_data = self._config.get("default_ranking", [])
        return [VoterConfig.from_dict(v) for v in ranking_data]

    def _load_voting_config(self) -> VotingConfig:
        """Load voting configuration from YAML."""
        voting_data = self._config.get("voting", {})
        return VotingConfig(
            consensus_mode=voting_data.get("consensus_mode", "unanimous"),
            consensus_boost=voting_data.get("consensus_boost", 0.15),
            weak_signal_boost=voting_data.get("weak_signal_boost", 0.10),
            conflict_penalty=voting_data.get("conflict_penalty", 0.20),
            strong_signal_size=voting_data.get("strong_signal_size", 1.0),
            weak_signal_size=voting_data.get("weak_signal_size", 0.5),
            conflict_size=voting_data.get("conflict_size", 0.0),
            min_data_points=voting_data.get("min_data_points", 42),
        )

    def _init_database(self) -> None:
        """Initialize SQLite database with voter_ranking_history table."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS voter_ranking_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ranking_json TEXT NOT NULL,
                    preset_name TEXT,
                    reason TEXT
                )
            """
            )
            conn.commit()
            conn.close()
            logger.debug(f"Initialized voter ranking table in {self._db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def _load_persisted_ranking(self) -> Optional[List[VoterConfig]]:
        """Load most recent voter ranking from database."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ranking_json FROM voter_ranking_history
                ORDER BY timestamp DESC LIMIT 1
            """
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                ranking_data = json.loads(row[0])
                return [VoterConfig.from_dict(v) for v in ranking_data]
            return None
        except Exception as e:
            logger.warning(f"Failed to load persisted ranking: {e}")
            return None

    def _save_ranking(
        self,
        ranking: List[VoterConfig],
        preset_name: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Save voter ranking to database."""
        try:
            ranking_json = json.dumps([v.to_dict() for v in ranking])
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO voter_ranking_history (timestamp, ranking_json, preset_name, reason)
                VALUES (?, ?, ?, ?)
            """,
                (now_iso(), ranking_json, preset_name, reason),
            )
            conn.commit()
            conn.close()
            logger.debug("Saved voter ranking to database")
        except Exception as e:
            logger.error(f"Failed to save ranking: {e}")

    # Public API

    def get_ranking(self) -> List[VoterConfig]:
        """Get current voter ranking."""
        return sorted(self._current_ranking, key=lambda v: v.rank)

    def get_active_voters(self) -> List[VoterConfig]:
        """Get only active voters (those that participate in decisions)."""
        return [v for v in self.get_ranking() if v.role == "active"]

    def get_review_voters(self) -> List[VoterConfig]:
        """Get review-only voters (shown but don't vote)."""
        return [v for v in self.get_ranking() if v.role == "review"]

    def get_active_voter_count(self) -> int:
        """Get number of active voters."""
        return len(self.get_active_voters())

    def get_voting_config(self) -> VotingConfig:
        """Get voting logic configuration."""
        return self._voting_config

    def get_indicator_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific indicator type."""
        indicators = self._config.get("indicators", {})
        return indicators.get(name)

    def get_available_indicators(self) -> List[str]:
        """Get list of available indicator types."""
        return list(self._config.get("indicators", {}).keys())

    def set_ranking(self, ranking: List[VoterConfig], reason: Optional[str] = None) -> None:
        """
        Update the current voter ranking.

        Args:
            ranking: New voter ranking list
            reason: Optional reason for the change
        """
        self._current_ranking = ranking
        self._save_ranking(ranking, reason=reason)
        logger.info(f"Updated voter ranking: {[v.name for v in ranking]}")

    def apply_preset(self, preset_name: str) -> bool:
        """
        Apply a preset ranking configuration.

        Args:
            preset_name: Name of preset from config

        Returns:
            True if preset was applied, False if not found
        """
        presets = self._config.get("presets", {})
        if preset_name not in presets:
            logger.warning(f"Preset not found: {preset_name}")
            return False

        preset = presets[preset_name]
        ranking_data = preset.get("ranking", [])
        ranking = [VoterConfig.from_dict(v) for v in ranking_data]

        self._current_ranking = ranking
        self._save_ranking(
            ranking, preset_name=preset_name, reason=f"Applied preset: {preset_name}"
        )
        logger.info(f"Applied preset '{preset_name}': {preset.get('description', '')}")
        return True

    def get_available_presets(self) -> Dict[str, str]:
        """Get available presets with descriptions."""
        presets = self._config.get("presets", {})
        return {name: p.get("description", "") for name, p in presets.items()}

    def promote_voter(self, name: str) -> bool:
        """
        Promote a voter one rank higher.

        Args:
            name: Name of voter to promote

        Returns:
            True if promoted, False if already at top or not found
        """
        ranking = self.get_ranking()
        voter_idx = next((i for i, v in enumerate(ranking) if v.name == name), None)

        if voter_idx is None:
            logger.warning(f"Voter not found: {name}")
            return False

        if voter_idx == 0:
            logger.info(f"Voter {name} already at top rank")
            return False

        # Swap with voter above
        ranking[voter_idx].rank, ranking[voter_idx - 1].rank = (
            ranking[voter_idx - 1].rank,
            ranking[voter_idx].rank,
        )
        self.set_ranking(ranking, reason=f"Promoted {name}")
        return True

    def demote_voter(self, name: str) -> bool:
        """
        Demote a voter one rank lower.

        Args:
            name: Name of voter to demote

        Returns:
            True if demoted, False if already at bottom or not found
        """
        ranking = self.get_ranking()
        voter_idx = next((i for i, v in enumerate(ranking) if v.name == name), None)

        if voter_idx is None:
            logger.warning(f"Voter not found: {name}")
            return False

        if voter_idx == len(ranking) - 1:
            logger.info(f"Voter {name} already at bottom rank")
            return False

        # Swap with voter below
        ranking[voter_idx].rank, ranking[voter_idx + 1].rank = (
            ranking[voter_idx + 1].rank,
            ranking[voter_idx].rank,
        )
        self.set_ranking(ranking, reason=f"Demoted {name}")
        return True

    def set_voter_role(self, name: str, role: str) -> bool:
        """
        Change a voter's role (active/review).

        Args:
            name: Name of voter
            role: New role ("active" or "review")

        Returns:
            True if changed, False if not found
        """
        if role not in ("active", "review"):
            logger.warning(f"Invalid role: {role}")
            return False

        for voter in self._current_ranking:
            if voter.name == name:
                old_role = voter.role
                voter.role = role
                self._save_ranking(
                    self._current_ranking, reason=f"Changed {name} role: {old_role} -> {role}"
                )
                logger.info(f"Changed {name} role from {old_role} to {role}")
                return True

        logger.warning(f"Voter not found: {name}")
        return False


# Singleton instance
_manager: Optional[RankedVoterManager] = None


def get_ranked_voter_manager() -> RankedVoterManager:
    """Get the global RankedVoterManager instance."""
    global _manager
    if _manager is None:
        _manager = RankedVoterManager()
    return _manager


def get_active_voters() -> List[VoterConfig]:
    """Get active voters from global manager."""
    return get_ranked_voter_manager().get_active_voters()


def get_voter_ranking() -> List[VoterConfig]:
    """Get full voter ranking from global manager."""
    return get_ranked_voter_manager().get_ranking()
