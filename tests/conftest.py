"""Shared fixtures for ask-cli tests."""

import json
import os
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyperclip
import pytest

from ask_cli import output
from ask_cli.cli import main
from ask_cli.config import (
    AppConfig,
    DefaultsConfig,
    FeaturesConfig,
    OutputConfig,
    ProviderConfig,
)

_ISOLATED_ENV_PREFIXES = ("ASK_", "WSL_", "XDG_")


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch) -> None:
    # Tests must never read real API keys, touch the real ~/.config/ask or
    # ~/.local/share/ask, or inherit WSL context from the host shell.
    for name in list(os.environ):
        if name.startswith(_ISOLATED_ENV_PREFIXES):
            monkeypatch.delenv(name)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))


@pytest.fixture(autouse=True)
def fake_clipboard(monkeypatch) -> list[str]:
    copied: list[str] = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)
    monkeypatch.setattr(pyperclip, "paste", lambda: copied[-1] if copied else "")
    return copied


@pytest.fixture(autouse=True)
def restore_output_consoles():
    # --no-color rebinds the module-level consoles and the code theme is module state; reset.
    original = (output.console, output.err_console, output._code_theme)
    yield
    output.console, output.err_console, output._code_theme = original


@pytest.fixture
def minimal_provider_config() -> ProviderConfig:
    return ProviderConfig(
        api_key="test-key",
        base_url="https://example.com",
        default_model="test-model",
        fast_model="test-fast-model",
        smart_model="test-smart-model",
    )


@pytest.fixture
def minimal_app_config(minimal_provider_config) -> AppConfig:
    return AppConfig(
        default_provider="zai",
        providers={
            "zai": minimal_provider_config,
            "anthropic": ProviderConfig(api_key="anthropic-key", default_model="claude-3"),
            "openai": ProviderConfig(api_key="openai-key", default_model="gpt-4o"),
            "google": ProviderConfig(api_key="google-key", default_model="gemini-1.5-flash"),
            "ollama": ProviderConfig(base_url="http://localhost:11434", default_model="llama3.2"),
        },
        defaults=DefaultsConfig(max_tokens=4096, quick_max_tokens=1024, history_ttl_hours=1),
        features=FeaturesConfig(),
        output=OutputConfig(),
    )


@pytest.fixture
def config_file(tmp_path) -> Path:
    """Return path to a temp config file with a valid minimal config."""
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "default_provider": "zai",
                "providers": {
                    "zai": {
                        "api_key": "sk-test",
                        "base_url": "https://api.z.ai/v1",
                        "default_model": "claude-sonnet-4-5-20251001",
                        "fast_model": "claude-haiku-4-5-20251001",
                        "smart_model": "claude-opus-4-5-20251001",
                    }
                },
            }
        )
    )
    return path


@dataclass
class CliRun:
    exit_code: int
    run_query: MagicMock
    run_agent: MagicMock
    history: MagicMock
    run_command: MagicMock


@pytest.fixture
def run_cli(minimal_app_config) -> Callable[..., CliRun]:
    # Runs `ask` end to end with the model, agent, history and shell stubbed out.
    # The loaded config is `minimal_app_config`: mutate that fixture to change it.
    def run(
        argv: list[str],
        *,
        response: str = "ok",
        run_query_error: BaseException | type[BaseException] | None = None,
        run_agent_error: BaseException | type[BaseException] | None = None,
        history_loaded: bool = True,
        history_error: BaseException | None = None,
        stop_reason: str | None = None,
        piped_stdin: str = "",
        stdin_tty: bool = True,
        input_answer: str | type[BaseException] | None = None,
        command_exit: int = 0,
    ) -> CliRun:
        if input_answer is None:
            input_patch = patch("builtins.input", side_effect=AssertionError("unexpected prompt"))
        elif isinstance(input_answer, str):
            input_patch = patch("builtins.input", return_value=input_answer)
        else:
            input_patch = patch("builtins.input", side_effect=input_answer)

        with ExitStack() as stack:
            stack.enter_context(patch("ask_cli.cli.load_config", return_value=minimal_app_config))
            stack.enter_context(patch("ask_cli.cli._read_piped_stdin", return_value=piped_stdin))
            stack.enter_context(patch("sys.stdin.isatty", return_value=stdin_tty))
            stack.enter_context(input_patch)
            history_class = stack.enter_context(patch("ask_cli.cli.ConversationHistory"))
            run_query = stack.enter_context(
                patch("ask_cli.cli.run_query", return_value=response, side_effect=run_query_error)
            )
            run_agent = stack.enter_context(
                patch("ask_cli.cli.run_agent", side_effect=run_agent_error)
            )
            run_command = stack.enter_context(
                patch("ask_cli.core.commands.run_command", return_value=command_exit)
            )
            if stop_reason is not None:
                provider = MagicMock(last_stop_reason=stop_reason)
                stack.enter_context(patch("ask_cli.cli.get_provider", return_value=provider))

            history = history_class.return_value
            history.messages = []
            history.load.return_value = history_loaded
            history.load.side_effect = history_error
            exit_code = main(argv)

        return CliRun(exit_code, run_query, run_agent, history, run_command)

    return run
