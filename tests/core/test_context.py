"""Tests for invocation-context detection (Linux vs Windows-via-WSL system prompt)."""

from unittest.mock import patch

import pytest

from ask_cli.config import DefaultsConfig

# --- ASK_CONTEXT system prompt selection ---


def test_default_context_uses_linux_system_prompt():
    """No ASK_CONTEXT (or any value other than 'windows') uses the Linux prompt."""
    from ask_cli.core.context import select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with patch.dict("os.environ", {}, clear=False):
        import os

        os.environ.pop("ASK_CONTEXT", None)
        assert select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_windows_context_uses_windows_system_prompt():
    """ASK_CONTEXT=windows selects the Windows prompt when not in an interactive WSL shell."""
    from ask_cli.core.context import select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.core.context.invocation_is_interactive_wsl", return_value=False),
    ):
        assert select_base_system_prompt(defaults) == "WINDOWS_PROMPT"


def test_windows_context_case_insensitive():
    """ASK_CONTEXT=WINDOWS (uppercase) also selects the Windows prompt."""
    from ask_cli.core.context import select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "WINDOWS"}),
        patch("ask_cli.core.context.invocation_is_interactive_wsl", return_value=False),
    ):
        assert select_base_system_prompt(defaults) == "WINDOWS_PROMPT"


def test_windows_context_falls_back_when_windows_prompt_empty():
    """If Windows prompt is empty, fall back to Linux prompt — backwards-safe."""
    from ask_cli.core.context import select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.core.context.invocation_is_interactive_wsl", return_value=False),
    ):
        assert select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_unknown_context_falls_back_to_linux():
    """ASK_CONTEXT=mac (or anything unknown) uses the Linux prompt."""
    from ask_cli.core.context import select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with patch.dict("os.environ", {"ASK_CONTEXT": "mac"}):
        assert select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_interactive_wsl_overrides_windows_context():
    """In an interactive WSL terminal, ASK_CONTEXT=windows (leaked via WSLENV) is ignored."""
    from ask_cli.core.context import select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.core.context.invocation_is_interactive_wsl", return_value=True),
    ):
        assert select_base_system_prompt(defaults) == "LINUX_PROMPT"


def test_non_interactive_wsl_keeps_windows_context():
    """wsl.exe from PowerShell: ASK_CONTEXT=windows set, no TTY → Windows prompt."""
    from ask_cli.core.context import select_base_system_prompt

    defaults = DefaultsConfig(
        system_prompt="LINUX_PROMPT",
        system_prompt_windows="WINDOWS_PROMPT",
    )
    with (
        patch.dict("os.environ", {"ASK_CONTEXT": "windows"}),
        patch("ask_cli.core.context.invocation_is_interactive_wsl", return_value=False),
    ):
        assert select_base_system_prompt(defaults) == "WINDOWS_PROMPT"


class TestInvocationIsInteractiveWsl:
    """The heuristic itself — three signals: WSL marker + TTY + interactive parent shell."""

    def test_requires_wsl_marker(self):
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch("ask_cli.core.context.parent_cmdline", return_value=["-bash"]),
        ):
            assert invocation_is_interactive_wsl() is False

    def test_requires_tty(self):
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=False),
            patch("sys.stdout.isatty", return_value=False),
            patch("ask_cli.core.context.parent_cmdline", return_value=["-bash"]),
        ):
            assert invocation_is_interactive_wsl() is False

    def test_parent_with_dash_c_is_not_interactive(self):
        """wsl.exe from PowerShell spawns `bash -c 'ask ...'` — parent has -c."""
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch(
                "ask_cli.core.context.parent_cmdline",
                return_value=["/bin/bash", "-c", "ask 'hello'"],
            ),
        ):
            assert invocation_is_interactive_wsl() is False

    def test_parent_is_init_is_not_interactive(self):
        """Some wsl.exe configs exec directly from /init without a shell layer."""
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch(
                "ask_cli.core.context.parent_cmdline",
                return_value=["/init", "ask", "hello"],
            ),
        ):
            assert invocation_is_interactive_wsl() is False

    def test_interactive_bash_parent_is_interactive(self):
        """User typing in a WSL terminal — parent is login bash `-bash` or `/bin/bash`, no -c."""
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch("ask_cli.core.context.parent_cmdline", return_value=["-bash"]),
        ):
            assert invocation_is_interactive_wsl() is True

    def test_non_login_interactive_bash_is_interactive(self):
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch("ask_cli.core.context.parent_cmdline", return_value=["/bin/bash"]),
        ):
            assert invocation_is_interactive_wsl() is True

    def test_wsl_interop_also_counts_as_wsl_marker(self):
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_INTEROP": "/run/WSL/42"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch("ask_cli.core.context.parent_cmdline", return_value=["-bash"]),
        ):
            assert invocation_is_interactive_wsl() is True

    def test_empty_parent_cmdline_bails_out(self):
        """If we can't read /proc (shouldn't happen on Linux), be conservative: not interactive."""
        from ask_cli.core.context import invocation_is_interactive_wsl

        with (
            patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch("ask_cli.core.context.parent_cmdline", return_value=[]),
        ):
            assert invocation_is_interactive_wsl() is False


@pytest.mark.parametrize(
    "parent",
    [["bash", "-lc", "ask hi"], ["zsh", "-ic", "ask hi"], ["/bin/sh", "-ec", "ask hi"]],
)
def test_clustered_c_option_is_not_interactive(parent):
    from ask_cli.core.context import invocation_is_interactive_wsl

    with (
        patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdout.isatty", return_value=True),
        patch("ask_cli.core.context.parent_cmdline", return_value=parent),
    ):
        assert invocation_is_interactive_wsl() is False


@pytest.mark.parametrize("parent", [["bash", "-l"], ["bash", "--login"], ["zsh", "-i"]])
def test_interactive_shell_options_without_c_stay_interactive(parent):
    from ask_cli.core.context import invocation_is_interactive_wsl

    with (
        patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdout.isatty", return_value=True),
        patch("ask_cli.core.context.parent_cmdline", return_value=parent),
    ):
        assert invocation_is_interactive_wsl() is True


def test_parent_cmdline_reads_the_real_parent_process():
    import os
    from pathlib import Path

    from ask_cli.core.context import parent_cmdline

    raw = Path(f"/proc/{os.getppid()}/cmdline").read_bytes()
    expected = raw.split(b"\0")[0].decode()
    assert parent_cmdline()[0] == expected


def test_parent_cmdline_is_empty_when_proc_is_unreadable():
    from ask_cli.core.context import parent_cmdline

    with patch("os.getppid", return_value=2**31 - 1):
        assert parent_cmdline() == []


def test_missing_stdin_is_treated_as_not_interactive():
    from ask_cli.core.context import invocation_is_interactive_wsl

    with (
        patch.dict("os.environ", {"WSL_DISTRO_NAME": "Ubuntu"}, clear=True),
        patch("sys.stdin", None),
    ):
        assert invocation_is_interactive_wsl() is False
