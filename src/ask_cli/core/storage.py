"""Atomic, owner-only JSON state files (history, stats, saved responses, config edits)."""

import contextlib
import json
import os
import tempfile
from pathlib import Path

from ask_cli.exceptions import StorageError


def ensure_private_dir(path: Path) -> None:
    """Create path (and parents) and restrict it to the owner."""
    path.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        path.chmod(0o700)


def read_json_object(path: Path) -> dict | None:
    """Return the JSON object stored at path, or None if the file does not exist.

    Raises StorageError if the file is unreadable, not UTF-8, not JSON, or not an object.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except UnicodeDecodeError as e:
        raise StorageError(f"{path} is corrupt (not UTF-8 text).") from e
    except OSError as e:
        raise StorageError(f"Cannot read {path}: {e.strerror or e}") from e
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise StorageError(f"{path} is corrupt (invalid JSON: {e.msg}).") from e
    if not isinstance(data, dict):
        raise StorageError(f"{path} is corrupt (expected a JSON object).")
    return data


def write_private_json(path: Path, data: dict) -> None:
    """Write data to path atomically with mode 0600. Raises StorageError on failure.

    The JSON goes to a temp file in the same directory (mkstemp creates it 0600)
    which then replaces the target, so a crash or Ctrl+C mid-write can never leave
    a truncated file, and the content is never briefly world-readable.
    """
    try:
        ensure_private_dir(path.parent)
        fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    except OSError as e:
        raise StorageError(f"Cannot write {path}: {e.strerror or e}") from e
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)
        temp_path.replace(path)
    except (OSError, TypeError, ValueError) as e:
        with contextlib.suppress(OSError):
            temp_path.unlink()
        raise StorageError(f"Cannot write {path}: {e}") from e
