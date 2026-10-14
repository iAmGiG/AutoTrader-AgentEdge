"""RankedVoterManager keeps its ranking in the shared state/user.db (isolated in tests)."""

from pathlib import Path

from src.core.ranked_voter_config import RankedVoterManager
from src.utils.state_paths import get_user_db_path


def test_ranking_db_is_the_shared_state_db(isolated_state_dir):
    manager = RankedVoterManager()

    assert manager._db_path == get_user_db_path()
    assert Path(manager._db_path).parent == isolated_state_dir
