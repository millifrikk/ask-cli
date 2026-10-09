"""Conversation history management — load, save, TTL expiry."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ask_cli.core.storage import read_json_object, write_private_json
from ask_cli.exceptions import HistoryError, StorageError

CLEAR_HINT = "Run `ask --clear` to start a fresh conversation."


class ConversationHistory:
    """Manages persistent conversation history with TTL-based expiry."""

    def __init__(self, path: Path, ttl_hours: int) -> None:
        self._path = path
        self._ttl_hours = ttl_hours
        self._messages: list[dict[str, str]] = []
        self._session_id: str = ""
        self._timestamp: datetime | None = None

    def load(self) -> bool:
        """Load history from disk. Returns False if expired or missing (not an error).

        Raises HistoryError if the file is unreadable or corrupt.
        """
        try:
            raw = read_json_object(self._path)
        except StorageError as e:
            raise HistoryError(f"Conversation history unusable: {e}", hint=CLEAR_HINT) from e
        if raw is None:
            self.start_new()
            return False

        timestamp_str = raw.get("timestamp", "")
        if not timestamp_str:
            self.start_new()
            return False

        try:
            saved_at = datetime.fromisoformat(timestamp_str)
            # Ensure timezone-aware comparison
            if saved_at.tzinfo is None:
                saved_at = saved_at.replace(tzinfo=UTC)
        except ValueError:
            self.start_new()
            return False

        now = datetime.now(tz=UTC)
        age_hours = (now - saved_at).total_seconds() / 3600
        if age_hours > self._ttl_hours:
            self.start_new()
            return False

        self._session_id = raw.get("session_id", uuid.uuid4().hex[:8])
        self._timestamp = saved_at
        self._messages = raw.get("messages", [])
        return True

    def start_new(self) -> None:
        """Begin a fresh session."""
        self._session_id = uuid.uuid4().hex[:8]
        self._timestamp = datetime.now(tz=UTC)
        self._messages = []

    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def save(self) -> None:
        """Write history to disk. Raises HistoryError on write failure."""
        data = {
            "session_id": self._session_id,
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "messages": self._messages,
        }
        try:
            write_private_json(self._path, data)
        except StorageError as e:
            raise HistoryError(f"Failed to save conversation history: {e}") from e

    def clear(self) -> None:
        """Delete history file and start a fresh session."""
        try:
            self._path.unlink(missing_ok=True)
        except OSError as e:
            raise HistoryError(f"Failed to clear conversation history {self._path}: {e}") from e
        self.start_new()

    @property
    def messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    @property
    def session_id(self) -> str:
        return self._session_id
