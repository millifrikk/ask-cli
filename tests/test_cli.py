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
        patch("ask_cli.output.pyperclip.copy") as mock_copy,
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
        patch("ask_cli.output.pyperclip.copy") as mock_copy,
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
        patch(
            "ask_cli.output.pyperclip.copy",
            side_effect=pyperclip.PyperclipException("no xclip"),
        ),
        patch("ask_cli.cli.record_query"),
        patch("ask_cli.output.render_warning") as mock_warn,
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


# --- ASK_CONTEXT system prompt selection ---


def test_default_context_uses_linux_system_prompt():
    """No ASK_CONTEXT (or any value other than 'windows') uses the Linux prompt."""
    from ask_cli.cli import _select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("ASK_CONTEXT", None)
        assert _select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_windows_context_uses_windows_system_prompt():
    """ASK_CONTEXT=windows selects the Windows prompt when not in an interactive WSL shell."""
    from ask_cli.cli import _select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.cli._invocation_is_interactive_wsl", return_value=False),
    ):
        assert _select_base_system_prompt(defaults) == "WINDOWS_PROMPT"


def test_windows_context_case_insensitive():
    """ASK_CONTEXT=WINDOWS (uppercase) also selects the Windows prompt."""
    from ask_cli.cli import _select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "WINDOWS"}),
        patch("ask_cli.cli._invocation_is_interactive_wsl", return_value=False),
    ):
        assert _select_base_system_prompt(defaults) == "WINDOWS_PROMPT"


def test_windows_context_falls_back_when_windows_prompt_empty():
    """If Windows prompt is empty, fall back to Linux prompt — backwards-safe."""
    from ask_cli.cli import _select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.cli._invocation_is_interactive_wsl", return_value=False),
    ):
        assert _select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_unknown_context_falls_back_to_linux():
    """ASK_CONTEXT=mac (or anything unknown) uses the Linux prompt."""
    from ask_cli.cli import _select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with patch.dict("os.environ", {"ASK_CONTEXT": "mac"}):
        assert _select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_interactive_wsl_overrides_windows_context():
    """In an interactive WSL terminal, ASK_CONTEXT=windows (leaked via WSLENV) is ignored."""
    from ask_cli.cli import _select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.cli._invocation_is_interactive_wsl", return_value=True),
    ):
        assert _select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_non_interactive_wsl_keeps_windows_context():
    """wsl.exe from PowerShell: ASK_CONTEXT=windows set, no TTY → Windows prompt."""
    from ask_cli.cli import _select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.cli._invocation_is_interactive_wsl", return_value=False),
    ):
        assert _select_base_system_prompt(defaults) == "WINDOWS_PROMPT"


class TestInvocationIsInteractiveWsl:
    """The heuristic itself."""

    def test_requires_wsl_marker(self):
        from ask_cli.cli import _invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
        ):
            assert _invocation_is_interactive_wsl() is False

    def test_requires_tty(self):
        from ask_cli.cli import _invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=False),
            patch("sys.stdout.isatty", return_value=False),
        ):
            assert _invocation_is_interactive_wsl() is False

    def test_wsl_plus_stdin_tty_is_interactive(self):
        from ask_cli.cli import _invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=False),
        ):
            assert _invocation_is_interactive_wsl() is True

    def test_wsl_plus_stdout_tty_is_interactive(self):
        """Redirected stdin but terminal stdout — user did `echo foo | ask` in WSL."""
        from ask_cli.cli import _invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=False),
            patch("sys.stdout.isatty", return_value=True),
        ):
            assert _invocation_is_interactive_wsl() is True

    def test_wsl_interop_also_counts_as_wsl_marker(self):
        from ask_cli.cli import _invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_INTEROP": "/run/WSL/42"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
        ):
            assert _invocation_is_interactive_wsl() is True


def test_set_default_provider_chmods_config(tmp_path):
    """--set-default-provider must re-apply chmod 600 after rewriting config.json."""
    import json

    from ask_cli.cli import _handle_set_default_provider

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"default_provider": "zai"}))
    config_path.chmod(0o644)  # simulate loose perms

    with (
        patch("ask_cli.cli.CONFIG_PATH", config_path),
        patch("ask_cli.cli.render_info"),
        patch("ask_cli.cli.render_error"),
    ):
        _handle_set_default_provider("anthropic")

    mode = config_path.stat().st_mode & 0o777
    assert mode == 0o600
