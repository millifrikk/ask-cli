"""Tests for the multi-step terminal agent."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from ask_cli.core.agent import run_agent
from ask_cli.core.commands import run_command_with_output


def _make_provider(*responses: str) -> MagicMock:
    """Create a mock provider whose stream() yields chunks from each response in turn."""
    provider = MagicMock()
    # Each call to stream() should return the next response as a single chunk
    provider.stream.side_effect = [iter([r]) for r in responses]
    return provider


def _run_agent_auto(provider, goal="do something", max_steps=5, log_path=None):
    if log_path is None:
        log_path = Path("/tmp/test_agent_log.txt")
    run_agent(
        goal=goal,
        provider=provider,
        model="test-model",
        max_tokens=512,
        base_system_prompt=None,
        max_steps=max_steps,
        auto_approve=True,
        log_path=log_path,
    )


def test_agent_calls_provider_stream(tmp_path):
    # Plan response + DONE (exec step 1)
    provider = _make_provider("1. echo hello", "DONE")
    with (
        patch("ask_cli.core.agent.render_info"),
        patch("ask_cli.core.agent.render_warning"),
    ):
        _run_agent_auto(provider, log_path=tmp_path / "log.txt")
    assert provider.stream.call_count >= 1


def test_agent_stops_on_done_response(tmp_path):
    provider = _make_provider("1. echo hello", "DONE")
    with (
        patch("ask_cli.core.agent.render_info") as mock_info,
        patch("ask_cli.core.agent.render_warning"),
    ):
        _run_agent_auto(provider, log_path=tmp_path / "log.txt")
    info_messages = [str(c) for c in mock_info.call_args_list]
    assert any("complete" in m or "Complete" in m for m in info_messages)
    # Only plan call + one exec call (DONE) = 2 total
    assert provider.stream.call_count == 2


def test_agent_stops_at_max_steps(tmp_path):
    # Plan + 3 exec responses (none are DONE)
    provider = _make_provider(
        "1. echo hi",
        "```bash\necho hi\n```",
        "```bash\necho hi\n```",
        "```bash\necho hi\n```",
    )
    with (
        patch("ask_cli.core.agent.render_info"),
        patch("ask_cli.core.agent.render_warning") as mock_warn,
        patch("ask_cli.core.agent.run_command_with_output", return_value=("hi", 0)),
        patch("ask_cli.core.agent.log_command"),
    ):
        _run_agent_auto(provider, max_steps=3, log_path=tmp_path / "log.txt")
    warn_messages = [str(c) for c in mock_warn.call_args_list]
    assert any("max steps" in m for m in warn_messages)


def test_agent_skips_when_no_command_found(tmp_path):
    # Plan + exec response — mock extract_command to return None
    provider = _make_provider("1. do the thing", "some prose without a fenced block")
    with (
        patch("ask_cli.core.agent.render_info"),
        patch("ask_cli.core.agent.render_warning") as mock_warn,
        patch("ask_cli.core.agent.extract_command", return_value=None),
    ):
        _run_agent_auto(provider, log_path=tmp_path / "log.txt")
    warn_messages = [str(c) for c in mock_warn.call_args_list]
    assert any("No command" in m for m in warn_messages)


def test_agent_auto_approve_skips_confirm(tmp_path):
    provider = _make_provider("1. echo hi", "```bash\necho hi\n```", "DONE")
    with (
        patch("ask_cli.core.agent.render_info"),
        patch("ask_cli.core.agent.render_warning"),
        patch("ask_cli.core.agent.run_command_with_output", return_value=("hi", 0)),
        patch("ask_cli.core.agent.log_command"),
        patch("ask_cli.core.agent._confirm") as mock_confirm,
    ):
        _run_agent_auto(provider, log_path=tmp_path / "log.txt")
    # auto_approve=True should never call _confirm for non-destructive commands
    mock_confirm.assert_not_called()


def test_agent_destructive_requires_confirm_even_with_auto_approve(tmp_path):
    # Plan + exec response with a destructive command
    provider = _make_provider("1. rm /tmp/x", "```bash\nrm /tmp/x\n```", "DONE")
    with (
        patch("ask_cli.core.agent.render_info"),
        patch("ask_cli.core.agent.render_warning"),
        patch("ask_cli.core.agent.run_command_with_output", return_value=("", 0)),
        patch("ask_cli.core.agent.log_command"),
        patch("ask_cli.core.agent._confirm", return_value=True) as mock_confirm,
    ):
        _run_agent_auto(provider, log_path=tmp_path / "log.txt")
    # _confirm must be called at least once for the destructive command
    mock_confirm.assert_called()


def test_run_command_with_output_captures_stdout():
    output, exit_code = run_command_with_output("echo hello")
    assert "hello" in output
    assert exit_code == 0


def test_run_command_with_output_returns_nonzero_exit_code():
    _output, exit_code = run_command_with_output("exit 42")
    assert exit_code == 42
