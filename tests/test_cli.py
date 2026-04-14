"""Tests for CLI argument parsing and flag combinations."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from ask_cli.config import (
    AppConfig,
    DefaultsConfig,
    FeaturesConfig,
    OfflineFallbackConfig,
    OutputConfig,
    ProviderConfig,
)


def _make_config(**provider_overrides) -> AppConfig:
    zai = ProviderConfig(
        api_key="key",
        default_model="claude-model",
        fast_model="claude-fast",
        smart_model="claude-smart",
    )
    return AppConfig(
        default_provider="zai",
        providers={"zai": zai, **provider_overrides},
        defaults=DefaultsConfig(),
        features=FeaturesConfig(),
        output=OutputConfig(),
        offline_fallback=OfflineFallbackConfig(),
    )


def _run_main(argv: list[str], config: AppConfig | None = None):
    if config is None:
        config = _make_config()
    with (
        patch("ask_cli.cli.load_config", return_value=config),
        patch("ask_cli.cli.run_query", return_value="response"),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_history_class,
    ):
        mock_history = MagicMock()
        mock_history_class.return_value = mock_history
        mock_history.messages = []
        with patch.object(sys, "argv", ["ask"] + argv):
            from ask_cli.cli import main

            main()
    return mock_history


def test_simple_query_calls_run_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="ok") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "hello", "world"]):
            from ask_cli.cli import main

            main()
        assert mock_run.called
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["query"] == "hello world"


def test_quick_flag_sets_low_max_tokens():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="ok") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--quick", "say something"]):
            from ask_cli.cli import main

            main()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["max_tokens"] == 1024


def test_continue_flag_loads_history():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="ok"),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "-c", "follow up"]):
            from ask_cli.cli import main

            main()
        mock_hist.load.assert_called_once()


def test_clear_flag_clears_history():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.render_info"),
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        with patch.object(sys, "argv", ["ask", "--clear"]):
            from ask_cli.cli import main

            main()
        mock_hist.clear.assert_called_once()


def test_list_providers_does_not_call_run_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query") as mock_run,
        patch("ask_cli.cli.render_provider_table"),
    ):
        with patch.object(sys, "argv", ["ask", "--list-providers"]):
            from ask_cli.cli import main

            main()
        mock_run.assert_not_called()


def test_explain_template_passed_to_run_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="ok") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--explain", "some code"]):
            from ask_cli.cli import main

            main()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["system_prompt"] is not None
        assert (
            "explain" in call_kwargs["system_prompt"].lower()
            or "explainer" in call_kwargs["system_prompt"].lower()
        )


def test_config_error_exits_with_code_1():
    from ask_cli.exceptions import ConfigError

    with (
        patch("ask_cli.cli.load_config", side_effect=ConfigError("bad config")),
        patch("ask_cli.cli.render_error"),
        pytest.raises(SystemExit) as exc_info,
        patch.object(sys, "argv", ["ask", "hello"]),
    ):
        from ask_cli.cli import main

        main()
    assert exc_info.value.code == 1


def test_no_query_exits_with_code_0(capsys):
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("sys.stdin.isatty", return_value=True),
        pytest.raises(SystemExit) as exc_info,
        patch.object(sys, "argv", ["ask"]),
    ):
        from ask_cli.cli import main

        main()
    assert exc_info.value.code == 0


def test_file_flag_prepends_to_query(tmp_path):
    f = tmp_path / "example.py"
    f.write_text("print('hello')")
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="ok") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "-f", str(f), "explain this"]):
            from ask_cli.cli import main

            main()
        call_kwargs = mock_run.call_args[1]
        assert "example.py" in call_kwargs["query"]
        assert "print('hello')" in call_kwargs["query"]
        assert "explain this" in call_kwargs["query"]


def test_missing_file_flag_exits():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.render_error"),
        patch("sys.stdin.isatty", return_value=True),
        pytest.raises(SystemExit) as exc_info,
        patch.object(sys, "argv", ["ask", "-f", "/no/such/file.txt", "q"]),
    ):
        from ask_cli.cli import main

        main()
    assert exc_info.value.code == 1


# --- domain mode tests ---


def test_domain_flag_sets_system_prompt():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="ok") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--docker", "optimise this"]):
            from ask_cli.cli import main

            main()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["system_prompt"] is not None
        assert "Docker" in call_kwargs["system_prompt"]


# --- save & recall tests ---


def test_recall_renders_without_running_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query") as mock_run,
        patch("ask_cli.cli.recall_response", return_value={"response": "stored answer"}),
        patch("ask_cli.cli.render_markdown"),
        patch.object(sys, "argv", ["ask", "--recall", "mykey"]),
    ):
        from ask_cli.cli import main

        main()
    mock_run.assert_not_called()


def test_save_flag_calls_save_after_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="the response"),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.save_response") as mock_save,
        patch("ask_cli.cli.render_info"),
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--save", "mykey", "my question"]):
            from ask_cli.cli import main

            main()
    mock_save.assert_called_once()
    call_args = mock_save.call_args[0]
    assert call_args[0] == "mykey"
    assert call_args[2] == "the response"


def test_list_saved_exits_without_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query") as mock_run,
        patch("ask_cli.cli.list_saved", return_value=[]),
        patch("ask_cli.cli.render_saved_list"),
        patch.object(sys, "argv", ["ask", "--list-saved"]),
    ):
        from ask_cli.cli import main

        main()
    mock_run.assert_not_called()


# --- command execution tests ---


def test_dry_run_does_not_execute():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="```bash\nls -la\n```"),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.run_command") as mock_run_cmd,
        patch("ask_cli.cli.render_info"),
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--cmd", "--dry-run", "list files"]):
            from ask_cli.cli import main

            main()
    mock_run_cmd.assert_not_called()


def test_cmd_injects_system_suffix():
    from ask_cli.core.commands import CMD_SYSTEM_SUFFIX

    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="```bash\nls\n```") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.render_info"),
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--cmd", "--dry-run", "find logs"]):
            from ask_cli.cli import main

            main()
    call_kwargs = mock_run.call_args[1]
    assert CMD_SYSTEM_SUFFIX in call_kwargs["system_prompt"]


# --- clipboard tests ---


def test_copy_flag_calls_pyperclip():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="full response text"),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.pyperclip.copy") as mock_copy,
        patch("ask_cli.cli.record_query"),
        patch("ask_cli.cli.render_info"),
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--copy", "q"]):
            from ask_cli.cli import main

            main()
    mock_copy.assert_called_once_with("full response text")


def test_copy_code_flag_extracts_block():
    response = "Here:\n```python\nprint('hi')\n```"
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value=response),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.pyperclip.copy") as mock_copy,
        patch("ask_cli.cli.record_query"),
        patch("ask_cli.cli.render_info"),
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--copy-code", "q"]):
            from ask_cli.cli import main

            main()
    mock_copy.assert_called_once_with("print('hi')")


def test_copy_warns_if_pyperclip_unavailable():
    import pyperclip

    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="some response"),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.pyperclip.copy", side_effect=pyperclip.PyperclipException("no xclip")),
        patch("ask_cli.cli.record_query"),
        patch("ask_cli.cli.render_warning") as mock_warn,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "--copy", "q"]):
            from ask_cli.cli import main

            main()
    mock_warn.assert_called()


# --- statistics CLI tests ---


def test_stats_flag_exits_without_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query") as mock_run,
        patch("ask_cli.cli.load_stats", return_value={}),
        patch("ask_cli.cli.render_stats"),
        patch.object(sys, "argv", ["ask", "--stats"]),
    ):
        from ask_cli.cli import main

        main()
    mock_run.assert_not_called()


def test_stats_reset_exits_without_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query") as mock_run,
        patch("ask_cli.cli.reset_stats"),
        patch("ask_cli.cli.render_info"),
        patch.object(sys, "argv", ["ask", "--stats-reset"]),
    ):
        from ask_cli.cli import main

        main()
    mock_run.assert_not_called()


def test_record_query_called_after_run_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query", return_value="the answer"),
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.ConversationHistory") as mock_hist_class,
        patch("ask_cli.cli.record_query") as mock_record,
    ):
        mock_hist = MagicMock()
        mock_hist_class.return_value = mock_hist
        mock_hist.messages = []
        with patch.object(sys, "argv", ["ask", "my question"]):
            from ask_cli.cli import main

            main()
    mock_record.assert_called_once()
    _path, mode, _in, _out = mock_record.call_args[0]
    assert mode == "default"


# --- agent CLI tests ---


def test_agent_flag_calls_run_agent():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.run_agent") as mock_agent,
        patch.object(sys, "argv", ["ask", "--agent", "list files"]),
    ):
        from ask_cli.cli import main

        main()
    mock_agent.assert_called_once()
    mock_run.assert_not_called()


def test_agent_does_not_call_run_query():
    with (
        patch("ask_cli.cli.load_config", return_value=_make_config()),
        patch("ask_cli.cli.run_query") as mock_run,
        patch("sys.stdin.isatty", return_value=True),
        patch("ask_cli.cli.run_agent"),
        patch.object(sys, "argv", ["ask", "--agent", "show disk usage"]),
    ):
        from ask_cli.cli import main

        main()
    mock_run.assert_not_called()
