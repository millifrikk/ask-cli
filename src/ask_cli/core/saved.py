"""Persist and retrieve named AI responses to/from disk."""

from datetime import UTC, datetime
from pathlib import Path

from ask_cli.core.storage import read_json_object, write_private_json
from ask_cli.exceptions import SavedResponseError, StorageError

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
    entry = {
        "name": name,
        "query": query,
        "response": response,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    try:
        write_private_json(saved_dir / f"{name}.json", entry)
    except StorageError as e:
        raise SavedResponseError(f"Failed to save response '{name}': {e}") from e


def recall_response(name: str, saved_dir: Path) -> dict:
    """Load a named response entry from disk. Raises SavedResponseError if not found."""
    _validate_name(name)
    try:
        entry = read_json_object(saved_dir / f"{name}.json")
    except StorageError as e:
        raise SavedResponseError(f"Failed to read saved response '{name}': {e}") from e
    if entry is None:
        raise SavedResponseError(
            f"No saved response named '{name}'.", hint="Run `ask --list-saved` to see names."
        )
    return entry


def list_saved(saved_dir: Path) -> list[dict]:
    """Return all saved entries sorted by timestamp descending (newest first).

    Unreadable files are listed with timestamp "unreadable" rather than hidden.
    """
    if not saved_dir.exists():
        return []
    entries: list[dict] = []
    for path in saved_dir.glob("*.json"):
        try:
            entry = read_json_object(path)
        except StorageError:
            entry = None
        entries.append(entry or {"name": path.stem, "timestamp": "unreadable"})
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
