"""Persist and retrieve named AI responses to/from disk."""

import json
from datetime import UTC, datetime
from pathlib import Path

from ask_cli.exceptions import SavedResponseError

_INVALID_CHARS = frozenset("/\\")


def _validate_name(name: str) -> None:
    if not name:
        raise SavedResponseError("Saved response name cannot be empty.")
    if name.startswith("."):
        raise SavedResponseError(f"Saved response name '{name}' must not start with '.'.")
    if any(c in name for c in _INVALID_CHARS):
        raise SavedResponseError(
            f"Saved response name '{name}' contains invalid characters (/ or \\)."
        )


def save_response(name: str, query: str, response: str, saved_dir: Path) -> None:
    """Write a named response entry to {saved_dir}/{name}.json."""
    _validate_name(name)
    saved_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "name": name,
        "query": query,
        "response": response,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    try:
        path = saved_dir / f"{name}.json"
        path.write_text(json.dumps(entry, indent=2))
        path.chmod(0o600)
    except OSError as e:
        raise SavedResponseError(f"Failed to save response '{name}': {e}") from e


def recall_response(name: str, saved_dir: Path) -> dict:
    """Load a named response entry from disk. Raises SavedResponseError if not found."""
    _validate_name(name)
    path = saved_dir / f"{name}.json"
    if not path.exists():
        raise SavedResponseError(f"No saved response named '{name}'.")
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise SavedResponseError(f"Failed to read saved response '{name}': {e}") from e


def list_saved(saved_dir: Path) -> list[dict]:
    """Return all saved entries sorted by timestamp descending (newest first)."""
    if not saved_dir.exists():
        return []
    entries: list[dict] = []
    for path in saved_dir.glob("*.json"):
        try:
            entry = json.loads(path.read_text())
            entries.append(entry)
        except (OSError, json.JSONDecodeError):
            continue
    entries.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return entries


def delete_saved(name: str, saved_dir: Path) -> None:
    """Delete a named response file. Raises SavedResponseError if not found."""
    _validate_name(name)
    path = saved_dir / f"{name}.json"
    if not path.exists():
        raise SavedResponseError(f"No saved response named '{name}'.")
    try:
        path.unlink()
    except OSError as e:
        raise SavedResponseError(f"Failed to delete saved response '{name}': {e}") from e
