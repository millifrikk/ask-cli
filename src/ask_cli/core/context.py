"""Invocation-context detection: Linux terminal vs. Windows (via wsl.exe) system prompt."""

import os
import sys

from ask_cli.config import DefaultsConfig


def parent_cmdline() -> list[str]:
    """Read `/proc/PPid/cmdline` (NUL-separated) and return argv as a list. Empty on failure."""
    try:
        with open(f"/proc/{os.getppid()}/cmdline", "rb") as f:
            raw = f.read().decode("utf-8", errors="replace")
        return [arg for arg in raw.split("\0") if arg]
    except OSError:
        return []


def _runs_a_command_string(argv: list[str]) -> bool:
    # `sh -c`, but also clustered short options like `bash -lc` or `zsh -ic`
    return any(
        arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:] for arg in argv[1:]
    )


def invocation_is_interactive_wsl() -> bool:
    """True if we're in an interactive WSL shell — user typed this, not proxied by wsl.exe.

    Three signals must all agree:
      1. We're in WSL (`WSL_DISTRO_NAME` or `WSL_INTEROP` set).
      2. At least one of stdin/stdout is a TTY. Under Windows Terminal + ConPTY
         this isn't enough on its own because wsl.exe proxies a TTY through.
      3. The parent process is an interactive shell — its argv has no `-c` (alone or
         clustered, e.g. `-lc`) and it isn't `/init`. `wsl.exe <cmd>` spawns
         `bash -c "<cmd>"`; a shell a user typed `ask "..."` into reads from a TTY.
    """
    try:
        in_wsl = bool(os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"))
        if not in_wsl:
            return False
        if not (sys.stdin.isatty() or sys.stdout.isatty()):
            return False
        argv = parent_cmdline()
        if not argv:
            return False
        if _runs_a_command_string(argv):
            return False
        return not (argv[0].endswith("/init") or argv[0] == "init")
    except (AttributeError, OSError):
        return False


def select_base_system_prompt(defaults: DefaultsConfig) -> str:
    """Pick the system prompt for the current invocation context.

    `ASK_CONTEXT=windows` selects the Windows/general prompt; anything else uses
    the Linux default. Set by the PowerShell wrapper (Path A) or the User-scope
    env var + WSLENV propagation (Path B).

    Because `WSLENV=ASK_CONTEXT/u` propagates the value into *every* WSL session
    — not just ones spawned by `wsl.exe` from PowerShell — we additionally
    override back to Linux when we can detect the user is typing directly in an
    interactive WSL terminal.
    """
    context = os.environ.get("ASK_CONTEXT", "linux").lower()
    if context == "windows" and invocation_is_interactive_wsl():
        context = "linux"
    if context == "windows" and defaults.system_prompt_windows:
        return defaults.system_prompt_windows
    return defaults.system_prompt
