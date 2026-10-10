"""Tests for CLI argument parsing and flag combinations."""

import json
import os
import sys
from unittest.mock import patch

import pyperclip
import pytest

from ask_cli.cli import _provider_hint, _read_piped_stdin, main, parse_args
from ask_cli.config import resolve_paths
from ask_cli.core.commands import CMD_SYSTEM_SUFFIX
from ask_cli.core.templates import BUILTIN_TEMPLATES, JSON_SYSTEM_SUFFIX
from ask_cli.exceptions import (
    ConfigError,
    HistoryError,
    ModelNotFoundError,
    ProviderError,
    SavedResponseError,
    StorageError,
    TemplateError,
)
from ask_cli.output import ConsoleUI

LS_BLOCK = "```bash\nls\n```"
PROSE_WITH_COMMAND = "Use:\n```bash\nls -la\n```"


def test_simple_query_calls_run_query(run_cli):
    run = run_cli(["hello", "world"])
    assert run.run_query.called
    assert run.run_query.call_args.kwargs["query"] == "hello world"


def test_quick_flag_sets_low_max_tokens(run_cli):
    run = run_cli(["--quick", "say something"])
    assert run.run_query.call_args.kwargs["max_tokens"] == 1024


def test_continue_flag_loads_history(run_cli):
    run = run_cli(["-c", "follow up"])
    run.history.load.assert_called_once()


def test_clear_flag_clears_history(run_cli):
    run = run_cli(["--clear"])
    run.history.clear.assert_called_once()


def test_list_providers_does_not_call_run_query(run_cli):
    run = run_cli(["--list-providers"])
    run.run_query.assert_not_called()


def test_explain_template_passed_to_run_query(run_cli):
    system_prompt = run_cli(["--explain", "some code"]).run_query.call_args.kwargs["system_prompt"]
    assert system_prompt is not None
    assert "explain" in system_prompt.lower() or "explainer" in system_prompt.lower()


def test_config_error_exits_with_code_1():
    with patch("ask_cli.cli.load_config", side_effect=ConfigError("bad config")):
        assert main(["hello"]) == 1


def test_no_query_prints_usage_to_stderr_and_exits_2(run_cli, capsys):
    assert run_cli([]).exit_code == 2
    captured = capsys.readouterr()
    assert "usage: ask" in captured.err
    assert captured.out == ""


def test_file_flag_prepends_to_query(run_cli, tmp_path):
    attached = tmp_path / "example.py"
    attached.write_text("print('hello')")
    query = run_cli(["-f", str(attached), "explain this"]).run_query.call_args.kwargs["query"]
    assert "example.py" in query
    assert "print('hello')" in query
    assert "explain this" in query


def test_missing_file_flag_exits(run_cli):
    assert run_cli(["-f", "/no/such/file.txt", "q"]).exit_code == 1


# --- domain mode tests ---


def test_domain_flag_sets_system_prompt(run_cli):
    run = run_cli(["--docker", "optimise this"])
    system_prompt = run.run_query.call_args.kwargs["system_prompt"]
    assert system_prompt is not None
    assert "Docker" in system_prompt


# --- save & recall tests ---


def test_recall_renders_without_running_query(run_cli):
    with patch("ask_cli.cli.recall_response", return_value={"response": "stored answer"}):
        run = run_cli(["--recall", "mykey"])
    run.run_query.assert_not_called()


def test_save_flag_calls_save_after_query(run_cli):
    with patch("ask_cli.cli.save_response") as mock_save:
        run_cli(["--save", "mykey", "my question"], response="the response")
    mock_save.assert_called_once()
    call_args = mock_save.call_args.args
    assert call_args[0] == "mykey"
    assert call_args[2] == "the response"


def test_list_saved_exits_without_query(run_cli):
    with patch("ask_cli.cli.list_saved", return_value=[]):
        run = run_cli(["--list-saved"])
    run.run_query.assert_not_called()


# --- command execution tests ---


def test_dry_run_does_not_execute(run_cli):
    run = run_cli(["--cmd", "--dry-run", "list files"], response="```bash\nls -la\n```")
    run.run_command.assert_not_called()


def test_cmd_injects_system_suffix(run_cli):
    run = run_cli(["--cmd", "--dry-run", "find logs"], response=LS_BLOCK)
    assert CMD_SYSTEM_SUFFIX in run.run_query.call_args.kwargs["system_prompt"]


# --- error boundary ---


def test_successful_query_returns_0(run_cli):
    assert run_cli(["hello"]).exit_code == 0


def test_history_error_is_rendered_with_hint_not_traceback(run_cli, capsys):
    error = HistoryError("Conversation history is corrupt.", hint="Run `ask --clear`.")
    assert run_cli(["-c", "hello"], history_error=error).exit_code == 1
    err = capsys.readouterr().err
    assert "Error: Conversation history is corrupt." in err
    assert "Run `ask --clear`." in err
    assert "Traceback" not in err


def test_provider_error_in_agent_mode_is_rendered(run_cli, capsys):
    error = ProviderError("Authentication failed.", provider="anthropic", status_code=401)
    assert run_cli(["--agent", "do it"], run_agent_error=error).exit_code == 1
    assert "Authentication failed." in capsys.readouterr().err


def test_ctrl_c_returns_130(run_cli):
    assert run_cli(["hello"], run_query_error=KeyboardInterrupt).exit_code == 130


def test_ctrl_c_during_agent_returns_130(run_cli):
    assert run_cli(["--agent", "do it"], run_agent_error=KeyboardInterrupt).exit_code == 130


def test_error_hint_from_exception_is_rendered(run_cli, capsys):
    error = TemplateError("Template 'x' not found.", hint="Check the templates directory.")
    with patch("ask_cli.cli.resolve_system_prompt", side_effect=error):
        assert run_cli(["--explain", "hello"]).exit_code == 1
    err = capsys.readouterr().err
    assert "Template 'x' not found." in err
    assert "Check the templates directory." in err


class TestProviderHint:
    def test_auth_failure_names_env_var(self):
        hint = _provider_hint(ProviderError("x", provider="anthropic", status_code=401))
        assert "ASK_ANTHROPIC_API_KEY" in hint

    def test_keyless_ollama_gets_no_api_key_hint(self):
        hint = _provider_hint(ProviderError("x", provider="ollama", status_code=401))
        assert hint is None or "API_KEY" not in hint

    def test_model_not_found_suggests_list_models(self):
        hint = _provider_hint(ModelNotFoundError("x", provider="zai", status_code=404))
        assert "ask -p zai --list-models" in hint

    def test_rate_limit_suggests_waiting(self):
        hint = _provider_hint(ProviderError("x", provider="openai", status_code=429))
        assert "try again" in hint


# --- local state failures ---


def test_stats_write_failure_warns_but_keeps_the_answer(run_cli, capsys):
    with patch("ask_cli.cli.record_query", side_effect=StorageError("disk full")):
        assert run_cli(["hello"]).exit_code == 0
    err = capsys.readouterr().err
    assert "Usage statistics not recorded" in err
    assert "disk full" in err


def test_corrupt_stats_file_gives_reset_hint(run_cli, capsys):
    stats_file = resolve_paths().stats_file
    stats_file.parent.mkdir(parents=True)
    stats_file.write_text("[]")
    assert run_cli(["--stats"]).exit_code == 1
    assert "ask --stats-reset" in capsys.readouterr().err


def test_stats_reset_failure_does_not_claim_success(run_cli, capsys):
    with patch("ask_cli.cli.reset_stats", side_effect=StorageError("read-only")):
        assert run_cli(["--stats-reset"]).exit_code == 1
    assert "Statistics reset." not in capsys.readouterr().err


def test_command_log_failure_warns_and_still_runs(run_cli, capsys):
    log_error = StorageError("Command not logged: x")
    with patch("ask_cli.core.commands.log_command", side_effect=log_error):
        run = run_cli(["--cmd", "--execute", "list files"], response=LS_BLOCK)
    assert run.exit_code == 0
    run.run_command.assert_called_once_with("ls")
    assert "Command not logged" in capsys.readouterr().err


# --- --cmd confirmation ---


def test_cmd_runs_after_y(run_cli):
    run = run_cli(["--cmd", "list"], response=LS_BLOCK, input_answer="y")
    assert run.exit_code == 0
    run.run_command.assert_called_once_with("ls")


def test_cmd_destructive_needs_exact_yes(run_cli):
    run = run_cli(["--cmd", "clean"], response="```bash\nrm -rf build\n```", input_answer="y")
    run.run_command.assert_not_called()


def test_cmd_eof_at_prompt_is_a_no_not_a_traceback(run_cli):
    run = run_cli(["--cmd", "list"], response=LS_BLOCK, input_answer=EOFError)
    assert run.exit_code == 0
    run.run_command.assert_not_called()


def test_cmd_with_piped_stdin_refuses_to_prompt(run_cli, capsys):
    # No input_answer: the fixture fails the test if a confirmation prompt is shown
    run = run_cli(["--cmd", "list"], response=LS_BLOCK, stdin_tty=False)
    assert run.exit_code == 0
    run.run_command.assert_not_called()
    assert "not a terminal" in capsys.readouterr().err


# --- piped stdin ---


class TestReadPipedStdin:
    def test_reads_from_a_pipe(self, monkeypatch):
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"  log line\n")
        os.close(write_fd)
        with os.fdopen(read_fd) as pipe:
            monkeypatch.setattr(sys, "stdin", pipe)
            assert _read_piped_stdin() == "log line"

    def test_reads_from_a_redirected_file(self, monkeypatch, tmp_path):
        source = tmp_path / "input.txt"
        source.write_text("from a file")
        with source.open() as file:
            monkeypatch.setattr(sys, "stdin", file)
            assert _read_piped_stdin() == "from a file"

    def test_ignores_character_devices_instead_of_blocking(self, monkeypatch):
        # /dev/null stands in for a TTY or an IDE's never-closed stdin
        with open("/dev/null") as device:
            monkeypatch.setattr(sys, "stdin", device)
            assert _read_piped_stdin() == ""

    def test_missing_or_unusable_stdin_is_empty(self, monkeypatch):
        monkeypatch.setattr(sys, "stdin", None)
        assert _read_piped_stdin() == ""


def test_piped_text_is_separated_from_the_question(run_cli):
    run = run_cli(["explain", "this"], piped_stdin="ERROR at line 3")
    assert run.run_query.call_args.kwargs["query"] == "explain this\n\nERROR at line 3"


# --- response feedback ---


def test_token_limit_cut_off_is_flagged(run_cli, capsys):
    run = run_cli(["--quick", "explain"], response="partial answ", stop_reason="max_tokens")
    assert run.exit_code == 0
    err = capsys.readouterr().err
    assert "cut off" in err
    assert "--quick" in err


def test_empty_response_is_an_error(run_cli, capsys):
    assert run_cli(["hello"], response="", stop_reason="end").exit_code == 1
    assert "empty response" in capsys.readouterr().err


def test_filtered_empty_response_says_why(run_cli, capsys):
    assert run_cli(["hello"], response="", stop_reason="filtered").exit_code == 1
    assert "content filter" in capsys.readouterr().err


def test_continue_without_recent_history_says_so(run_cli, capsys):
    run = run_cli(["-c", "and then?"], stop_reason="end", history_loaded=False)
    assert run.exit_code == 0
    assert "starting a new conversation" in capsys.readouterr().err


def test_failed_command_is_reported_but_does_not_change_ask_exit_code(run_cli, capsys):
    run = run_cli(["--cmd", "--execute", "list"], response=LS_BLOCK, command_exit=3)
    assert run.exit_code == 0
    assert "exited with code 3" in capsys.readouterr().err


def test_confirmed_command_failure_is_reported(run_cli, capsys):
    run = run_cli(["--cmd", "list"], response=LS_BLOCK, input_answer="y", command_exit=2)
    assert run.exit_code == 0
    assert "exited with code 2" in capsys.readouterr().err


# --- clipboard behaviour ---


def test_cmd_auto_copies_the_command(run_cli, fake_clipboard):
    assert run_cli(["--cmd", "--dry-run", "list files"], response=PROSE_WITH_COMMAND).exit_code == 0
    assert fake_clipboard == ["ls -la"]


def test_cmd_auto_copy_respects_clipboard_setting(run_cli, minimal_app_config, fake_clipboard):
    minimal_app_config.features.clipboard = False
    assert run_cli(["--cmd", "--dry-run", "list files"], response=PROSE_WITH_COMMAND).exit_code == 0
    assert fake_clipboard == []


def test_explicit_copy_code_overrides_clipboard_setting(
    run_cli, minimal_app_config, fake_clipboard
):
    minimal_app_config.features.clipboard = False
    argv = ["--cmd", "--dry-run", "--copy-code", "list files"]
    assert run_cli(argv, response=PROSE_WITH_COMMAND).exit_code == 0
    assert fake_clipboard == ["ls -la"]


def test_cmd_with_copy_copies_once(run_cli, fake_clipboard):
    argv = ["--cmd", "--dry-run", "--copy", "list files"]
    assert run_cli(argv, response=PROSE_WITH_COMMAND).exit_code == 0
    assert len(fake_clipboard) == 1


# --- --save ---


def test_invalid_save_name_fails_before_calling_the_model(run_cli, capsys):
    run = run_cli(["--save", ".hidden", "question"])
    assert run.exit_code == 1
    run.run_query.assert_not_called()
    assert "must not start with '.'" in capsys.readouterr().err


def test_save_failure_after_answer_exits_1(run_cli, capsys):
    with patch("ask_cli.cli.save_response", side_effect=SavedResponseError("disk full")):
        assert run_cli(["--save", "notes", "question"]).exit_code == 1
    assert "disk full" in capsys.readouterr().err


def test_agent_receives_prompt_dry_run_think_and_a_console_ui(run_cli):
    run = run_cli(["--agent", "--dry-run", "--quick", "--docker", "tidy up"])
    assert run.exit_code == 0
    kwargs = run.run_agent.call_args.kwargs
    assert CMD_SYSTEM_SUFFIX not in kwargs["base_system_prompt"]
    assert kwargs["dry_run"] is True
    assert kwargs["think"] is False
    assert "Docker" in kwargs["base_system_prompt"]
    assert kwargs["max_steps"] == 10
    assert isinstance(kwargs["ui"], ConsoleUI)


# --- flag semantics ---


@pytest.mark.parametrize(
    "argv",
    [
        ["--fast", "--smart", "q"],
        ["-m", "some-model", "--fast", "q"],
        ["--raw", "--json", "q"],
        ["--markdown", "--code-only", "q"],
        ["--explain", "--fix", "q"],
        ["--sql", "--docker", "q"],
        ["--stats", "--list-saved"],
        ["--clear", "a new question"],
        ["--stats", "q"],
        ["--auto-approve", "q"],
        ["--agent-max-steps", "3", "q"],
        ["--agent", "--save", "n", "q"],
        ["--agent", "-c", "q"],
        ["--agent", "--copy", "q"],
        ["--agent", "--cmd", "q"],
        ["--execute", "--dry-run", "q"],
        ["--agent", "--agent-max-steps", "0", "q"],
        ["--max-file-size", "0", "q"],
        ["--max-file-size", "-5", "q"],
        ["-p", "bogus", "q"],
        ["--set-default-provider", "bogus"],
    ],
)
def test_conflicting_or_invalid_flags_are_usage_errors(argv, minimal_app_config, capsys):
    with patch("ask_cli.cli.load_config", return_value=minimal_app_config) as load:
        with pytest.raises(SystemExit) as exc_info:
            main(argv)
        load.assert_not_called()
    assert exc_info.value.code == 2
    assert "error:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [["--list-models", "-p", "zai"], ["--agent", "--dry-run", "q"], ["--fast", "--quick", "q"]],
)
def test_compatible_flags_are_accepted(argv):
    parse_args(argv)


def test_execute_implies_cmd_mode(run_cli):
    run = run_cli(["--execute", "list files"], response="no command here")
    assert CMD_SYSTEM_SUFFIX in run.run_query.call_args.kwargs["system_prompt"]


def test_domain_and_task_flags_compose(run_cli):
    run = run_cli(["--docker", "--fix", "my container exits"])
    prompt = run.run_query.call_args.kwargs["system_prompt"]
    assert BUILTIN_TEMPLATES["docker"] in prompt
    assert BUILTIN_TEMPLATES["fix"] in prompt


def test_template_flag_uses_user_yaml(run_cli):
    templates_dir = resolve_paths().templates_dir
    templates_dir.mkdir(parents=True)
    (templates_dir / "reviewer.yaml").write_text("prompt: Review like a grumpy senior.\n")
    run = run_cli(["--template", "reviewer", "check this"])
    assert "Review like a grumpy senior." in run.run_query.call_args.kwargs["system_prompt"]


# --- json mode ---


def test_json_injects_json_only_system_suffix(run_cli):
    run = run_cli(["--json", "list distros"], response='{"a": 1}')
    assert run.run_query.call_args.kwargs["system_prompt"].endswith(JSON_SYSTEM_SUFFIX)


def test_non_json_modes_do_not_get_json_suffix(run_cli):
    run = run_cli(["--raw", "list distros"], response="text")
    assert JSON_SYSTEM_SUFFIX not in (run.run_query.call_args.kwargs["system_prompt"] or "")


def test_json_warns_on_stderr_when_response_is_not_json(run_cli, capsys):
    run_cli(["--json", "list distros"], response="1. Ubuntu\n2. Fedora")
    captured = capsys.readouterr()
    assert "not valid JSON" in captured.err
    assert "not valid JSON" not in captured.out


def test_json_fenced_valid_response_does_not_warn(run_cli, capsys):
    run_cli(["--json", "list distros"], response='```json\n["ubuntu"]\n```')
    assert "not valid JSON" not in capsys.readouterr().err


# --- clipboard tests ---


def test_copy_flag_calls_pyperclip(run_cli, fake_clipboard):
    run_cli(["--copy", "q"], response="full response text")
    assert fake_clipboard == ["full response text"]


def test_copy_code_flag_extracts_block(run_cli, fake_clipboard):
    run_cli(["--copy-code", "q"], response="Here:\n```python\nprint('hi')\n```")
    assert fake_clipboard == ["print('hi')"]


def test_copy_warns_if_pyperclip_unavailable(run_cli):
    with (
        patch(
            "ask_cli.output.pyperclip.copy",
            side_effect=pyperclip.PyperclipException("no xclip"),
        ),
        patch("ask_cli.output.render_warning") as mock_warn,
    ):
        run_cli(["--copy", "q"], response="some response")
    mock_warn.assert_called()


# --- statistics CLI tests ---


def test_stats_flag_exits_without_query(run_cli):
    with patch("ask_cli.cli.load_stats", return_value={}):
        run = run_cli(["--stats"])
    run.run_query.assert_not_called()


def test_stats_reset_exits_without_query(run_cli):
    with patch("ask_cli.cli.reset_stats"):
        run = run_cli(["--stats-reset"])
    run.run_query.assert_not_called()


def test_record_query_called_after_run_query(run_cli):
    with patch("ask_cli.cli.record_query") as mock_record:
        run_cli(["my question"], response="the answer")
    mock_record.assert_called_once()
    _path, mode, _in, _out = mock_record.call_args.args
    assert mode == "default"


# --- agent CLI tests ---


def test_agent_flag_calls_run_agent(run_cli):
    run = run_cli(["--agent", "list files"])
    run.run_agent.assert_called_once()
    run.run_query.assert_not_called()


def test_agent_does_not_call_run_query(run_cli):
    run = run_cli(["--agent", "show disk usage"])
    run.run_query.assert_not_called()


def test_set_default_provider_updates_the_real_config_file(capsys):
    assert main(["--set-default-provider", "anthropic"]) == 0
    saved = json.loads(resolve_paths().config_file.read_text())
    assert saved["default_provider"] == "anthropic"
    assert "Default provider set to 'anthropic'" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "mode"),
    [
        (["hello"], "default"),
        (["--quick", "hello"], "quick"),
        (["--docker", "--fix", "hello"], "docker+fix"),
        (["--cmd", "--dry-run", "list"], "cmd"),
        (["--agent", "--dry-run", "tidy"], "agent"),
    ],
)
def test_stats_record_the_mode_used(run_cli, argv, mode):
    with patch("ask_cli.cli.record_query") as record_query:
        assert run_cli(argv, response=LS_BLOCK).exit_code == 0
    assert record_query.call_args.args[1] == mode


def test_configured_code_theme_is_applied(run_cli, minimal_app_config):
    minimal_app_config.output.code_theme = "dracula"
    with patch("ask_cli.cli.set_code_theme") as set_code_theme:
        assert run_cli(["hello"]).exit_code == 0
    set_code_theme.assert_called_once_with("dracula")


def test_config_warnings_are_rendered(run_cli, minimal_app_config, capsys):
    minimal_app_config.warnings.append("Provider 'zai' base_url is risky.")
    assert run_cli(["hello"]).exit_code == 0
    assert "base_url is risky" in capsys.readouterr().err


def test_ask_context_windows_no_longer_changes_the_prompt(run_cli, minimal_app_config, monkeypatch):
    minimal_app_config.defaults.system_prompt = "LINUX_PROMPT"
    # A leftover Windows prompt (old config) must not be picked up any more
    minimal_app_config.defaults.system_prompt_windows = "WINDOWS_PROMPT"
    monkeypatch.setenv("ASK_CONTEXT", "windows")
    run = run_cli(["hello"])
    assert run.run_query.call_args.kwargs["system_prompt"] == "LINUX_PROMPT"
