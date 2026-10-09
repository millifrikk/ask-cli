"""Tests for run_query() — streaming accumulation, Ctrl+C, history."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ask_cli.core.conversation import run_query
from ask_cli.core.history import ConversationHistory


def _make_provider(chunks: list[str]):
    provider = MagicMock()
    provider.stream.return_value = iter(chunks)
    return provider


def _make_history(tmp_path: Path) -> ConversationHistory:
    h = ConversationHistory(tmp_path / "history.json", ttl_hours=1)
    h.start_new()
    return h


@pytest.fixture
def tmp_history(tmp_path):
    return _make_history(tmp_path)


def _run(provider, history, use_history=False, on_chunk=None):
    return run_query(
        query="test query",
        provider=provider,
        model="model",
        max_tokens=100,
        system_prompt=None,
        history=history,
        use_history=use_history,
        on_chunk=on_chunk or (lambda chunk: None),
    )


def test_run_query_forwards_each_chunk_in_order(tmp_history):
    received: list[str] = []
    _run(_make_provider(["a", "b", "c"]), tmp_history, on_chunk=received.append)
    assert received == ["a", "b", "c"]


def test_run_query_returns_full_response(tmp_history):
    provider = _make_provider(["Hello", ", ", "world!"])
    result = _run(provider, tmp_history)
    assert result == "Hello, world!"


def test_run_query_saves_to_history_when_use_history(tmp_history):
    provider = _make_provider(["answer"])
    _run(provider, tmp_history, use_history=True)
    assert len(tmp_history.messages) == 2
    assert tmp_history.messages[0] == {"role": "user", "content": "test query"}
    assert tmp_history.messages[1] == {"role": "assistant", "content": "answer"}


def test_run_query_always_saves_history(tmp_history):
    # History is saved after every query so that -c can continue any previous exchange.
    provider = _make_provider(["answer"])
    _run(provider, tmp_history, use_history=False)
    assert len(tmp_history.messages) == 2
    assert tmp_history.messages[0] == {"role": "user", "content": "test query"}
    assert tmp_history.messages[1] == {"role": "assistant", "content": "answer"}


def test_run_query_prepends_history_messages(tmp_path):
    history = ConversationHistory(tmp_path / "h.json", ttl_hours=1)
    history.start_new()
    history.add_user_message("prior question")
    history.add_assistant_message("prior answer")

    provider = _make_provider(["new answer"])

    run_query(
        query="follow up",
        provider=provider,
        model="model",
        max_tokens=100,
        system_prompt=None,
        history=history,
        use_history=True,
        on_chunk=lambda chunk: None,
    )

    call_args = provider.stream.call_args
    messages = call_args[0][0]
    assert messages[0]["content"] == "prior question"
    assert messages[1]["content"] == "prior answer"
    assert messages[2]["content"] == "follow up"


def test_keyboard_interrupt_saves_partial_response(tmp_path):
    """Ctrl+C mid-stream should save partial response with [interrupted] suffix."""
    history = _make_history(tmp_path)

    provider = MagicMock()

    def _raise_after_first(messages, model, max_tokens, system_prompt, **kwargs):
        yield "partial"
        raise KeyboardInterrupt

    provider.stream.side_effect = _raise_after_first

    result = run_query(
        query="test",
        provider=provider,
        model="model",
        max_tokens=100,
        system_prompt=None,
        history=history,
        use_history=True,
        on_chunk=lambda chunk: None,
    )

    assert result == "partial"
    # Partial response should be in history with [interrupted] suffix
    assert len(history.messages) == 2
    assert "[interrupted]" in history.messages[1]["content"]
