"""Usage statistics tracking for ask-cli."""

import copy
import json
from datetime import UTC, datetime
from pathlib import Path

EMPTY_STATS: dict = {
    "total_queries": 0,
    "input_chars": 0,
    "output_chars": 0,
    "queries_by_mode": {},
    "first_use": None,
    "last_use": None,
}


def load_stats(stats_path: Path) -> dict:
    """Load stats from disk; return EMPTY_STATS copy if missing or corrupt."""
    if not stats_path.exists():
        return copy.deepcopy(EMPTY_STATS)
    try:
        return json.loads(stats_path.read_text())
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(EMPTY_STATS)


def record_query(
    stats_path: Path,
    mode: str,
    input_chars: int,
    output_chars: int,
) -> None:
    """Increment counters and persist. Silent on OSError."""
    try:
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

        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(stats, indent=2))
    except OSError:
        pass


def reset_stats(stats_path: Path) -> None:
    """Write EMPTY_STATS to disk. Silent on OSError."""
    try:
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(dict(EMPTY_STATS), indent=2))
    except OSError:
        pass
