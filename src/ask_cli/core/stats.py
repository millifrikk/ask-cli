"""Usage statistics tracking for ask-cli."""

import copy
from datetime import UTC, datetime
from pathlib import Path

from ask_cli.core.storage import read_json_object, write_private_json
from ask_cli.exceptions import StorageError

EMPTY_STATS: dict = {
    "total_queries": 0,
    "input_chars": 0,
    "output_chars": 0,
    "queries_by_mode": {},
    "first_use": None,
    "last_use": None,
}


RESET_HINT = "Run `ask --stats-reset` to start fresh statistics."


def load_stats(stats_path: Path) -> dict:
    """Load stats from disk; an EMPTY_STATS copy if the file doesn't exist yet.

    Raises StorageError (with a reset hint) if the file is unreadable or corrupt.
    """
    try:
        stats = read_json_object(stats_path)
    except StorageError as e:
        raise StorageError(str(e), hint=RESET_HINT) from e
    return copy.deepcopy(EMPTY_STATS) if stats is None else stats


def record_query(
    stats_path: Path,
    mode: str,
    input_chars: int,
    output_chars: int,
) -> None:
    """Increment counters and persist. Raises StorageError on failure."""
    stats = load_stats(stats_path)
    stats["total_queries"] = stats.get("total_queries", 0) + 1
    stats["input_chars"] = stats.get("input_chars", 0) + input_chars
    stats["output_chars"] = stats.get("output_chars", 0) + output_chars

    by_mode = stats.get("queries_by_mode", {})
    by_mode[mode] = by_mode.get(mode, 0) + 1
    stats["queries_by_mode"] = by_mode

    now = datetime.now(UTC).isoformat()
    if stats.get("first_use") is None:
        stats["first_use"] = now
    stats["last_use"] = now

    write_private_json(stats_path, stats)


def reset_stats(stats_path: Path) -> None:
    """Overwrite stats with EMPTY_STATS (also repairs a corrupt file). Raises StorageError."""
    write_private_json(stats_path, copy.deepcopy(EMPTY_STATS))
