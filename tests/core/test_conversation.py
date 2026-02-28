"""Tests for run_query() — streaming accumulation, Ctrl+C, history."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ask_cli.core.conversation import _render_code_blocks, run_query
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


def _run(provider, history, use_history=False, output_mode="raw"):
    with (
        patch("ask_cli.core.conversation.Live"),
        patch("ask_cli.core.conversation.render_raw"),
        patch("ask_cli.core.conversation.render_code"),
    ):
        return run_query(
            query="test query",
            provider=provider,
            model="model",
            max_tokens=100,
            system_prompt=None,
            history=history,
            use_history=use_history,
            output_mode=output_mode,
        )


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

    with patch("ask_cli.core.conversation.Live"), patch("ask_cli.core.conversation.render_raw"):
        run_query(
            query="follow up",
            provider=provider,
            model="model",
            max_tokens=100,
            system_prompt=None,
            history=history,
            use_history=True,
            output_mode="raw",
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

    def _raise_after_first(messages, model, max_tokens, system_prompt):
        yield "partial"
        raise KeyboardInterrupt

    provider.stream.side_effect = _raise_after_first

    with (
        patch("ask_cli.core.conversation.Live") as mock_live_class,
        patch("ask_cli.core.conversation.render_raw"),
    ):
        # Make Live context manager work, but let KeyboardInterrupt propagate from the for loop
        mock_live = MagicMock()
        mock_live_class.return_value.__enter__ = MagicMock(return_value=mock_live)
        mock_live_class.return_value.__exit__ = MagicMock(return_value=False)

        run_query(
            query="test",
            provider=provider,
            model="model",
            max_tokens=100,
            system_prompt=None,
            history=history,
            use_history=True,
            output_mode="raw",
        )

    # Partial response should be in history with [interrupted] suffix
    assert len(history.messages) == 2
    assert "[interrupted]" in history.messages[1]["content"]


class TestRenderCodeBlocks:
    def test_extracts_code_block(self):
        text = "```python\nprint('hi')\n```"
        with patch("ask_cli.core.conversation.render_code") as mock_render:
            _render_code_blocks(text)
            mock_render.assert_called_once_with("print('hi')", language="python")

    def test_falls_back_to_raw_when_no_code_blocks(self):
        text = "No code here."
        with patch("ask_cli.core.conversation.render_raw") as mock_raw:
            _render_code_blocks(text)
            mock_raw.assert_called_once_with(text)

    def test_multiple_code_blocks(self):
        text = "```python\nfoo()\n```\n\n```bash\necho hi\n```"
        with patch("ask_cli.core.conversation.render_code") as mock_render:
            _render_code_blocks(text)
            assert mock_render.call_count == 2
