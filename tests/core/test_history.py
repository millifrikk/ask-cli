"""Tests for ConversationHistory load/save/TTL/clear."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ask_cli.core.history import ConversationHistory
from ask_cli.exceptions import HistoryError


@pytest.fixture
def history_path(tmp_path) -> Path:
    return tmp_path / "history.json"


def test_load_returns_false_when_no_file(history_path):
    h = ConversationHistory(history_path, ttl_hours=1)
    result = h.load()
    assert result is False
    assert h.messages == []
    assert h.session_id != ""


def test_load_returns_true_and_restores_messages(history_path):
    now = datetime.now(tz=UTC).isoformat()
    history_path.write_text(
        json.dumps(
            {
                "session_id": "abc123",
                "timestamp": now,
                "messages": [
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "world"},
                ],
            }
        )
    )

    h = ConversationHistory(history_path, ttl_hours=1)
    result = h.load()
    assert result is True
    assert len(h.messages) == 2
    assert h.messages[0]["content"] == "hello"
    assert h.session_id == "abc123"


def test_load_returns_false_on_ttl_expiry(history_path):
    old_time = (datetime.now(tz=UTC) - timedelta(hours=2)).isoformat()
    history_path.write_text(
        json.dumps(
            {
                "session_id": "old",
                "timestamp": old_time,
                "messages": [{"role": "user", "content": "stale"}],
            }
        )
    )

    h = ConversationHistory(history_path, ttl_hours=1)
    result = h.load()
    assert result is False
    assert h.messages == []  # expired history discarded


def test_load_raises_on_corrupt_json(history_path):
    history_path.write_text("{ not json }")
    h = ConversationHistory(history_path, ttl_hours=1)
    with pytest.raises(HistoryError, match="Failed to read"):
        h.load()


def test_save_roundtrip(history_path):
    h = ConversationHistory(history_path, ttl_hours=1)
    h.start_new()
    h.add_user_message("hello")
    h.add_assistant_message("world")
    h.save()

    assert history_path.exists()
    data = json.loads(history_path.read_text())
    assert len(data["messages"]) == 2
    assert data["messages"][0] == {"role": "user", "content": "hello"}


def test_save_writes_mode_0600(history_path):
    h = ConversationHistory(history_path, ttl_hours=1)
    h.start_new()
    h.add_user_message("secret stuff")
    h.save()

    mode = history_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_clear_removes_file_and_starts_fresh(history_path):
    h = ConversationHistory(history_path, ttl_hours=1)
    h.start_new()
    h.add_user_message("hello")
    h.save()
    assert history_path.exists()

    h.clear()
    assert not history_path.exists()
    assert h.messages == []


def test_messages_returns_defensive_copy(history_path):
    h = ConversationHistory(history_path, ttl_hours=1)
    h.start_new()
    h.add_user_message("hello")

    messages = h.messages
    messages.append({"role": "user", "content": "injected"})
    assert len(h.messages) == 1  # internal state unchanged


def test_naive_timestamp_handled(history_path):
    """Naive timestamps (no timezone) in stored history should be handled without error."""
    naive_time = (datetime.now() - timedelta(minutes=5)).isoformat()  # no tz
    history_path.write_text(
        json.dumps(
            {
                "session_id": "s1",
                "timestamp": naive_time,
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
    )

    h = ConversationHistory(history_path, ttl_hours=1)
    # Should not raise — naive timestamps are treated as UTC
    result = h.load()
    assert result is True
