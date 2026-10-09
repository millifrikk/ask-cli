"""Shell command extraction, safety checks, and execution for ask-cli."""

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ask_cli.core.fences import extract_code_blocks
from ask_cli.core.storage import ensure_private_dir
from ask_cli.exceptions import StorageError

CMD_SYSTEM_SUFFIX = (
    "Return ONLY a single executable shell command in a fenced code block (```bash ... ```). "
    "Do not include explanations. If multiple steps are needed, chain them with && or ||."
)

# Commands that need explicit confirmation even under --execute / --auto-approve.
# Best-effort: matched against the command after stripping quotes and backslashes,
# so `r\m` and `'rm'` can't slip past. Deliberately errs towards asking.
DESTRUCTIVE_PATTERNS = [
    # Deleting, overwriting, moving
    r"\brm\b",
    r"\bmv\b",
    r"\bshred\b",
    r"\bdd\b",
    r"\btruncate\b",
    r"\bwipe\b",
    r"\bfind\b.*\s-delete\b",
    r"\bfind\b.*\s-exec\b",
    r"\brsync\b.*\s--delete",
    r"\btee\b(?!\s+(-a\s+)?/dev/null\b)",
    # Output redirection to a file — except /dev/null, scratch files directly under /tmp
    # (no ".." escapes) and fd duplication like 2>&1
    r"(?<![<>&])\d*>>?(?!\s*(/dev/null\b|/tmp/(?![^\s]*\.\.)|&\d))",
    # Disks and the system
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bkill\b",
    r"\bkillall\b",
    r"\bsystemctl\s+(stop|disable|mask|restart)\b",
    r"\bcrontab\s+-r\b",
    # Permissions and privilege
    r"\bchmod\b",
    r"\bchown\b",
    r"\bchattr\b",
    r"\bsudo\b",
    r"\bdoas\b",
    # Git: discarding work or publishing it
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b",
    r"\bgit\s+checkout\s+(--\s|\.(\s|$))",
    r"\bgit\s+restore\b",
    r"\bgit\s+branch\s+-D\b",
    r"\bgit\s+stash\s+(drop|clear)\b",
    r"\bgit\s+push\b",
    # Running code that isn't visible in the command itself
    r"\|\s*(sudo\s+)?(sh|bash|zsh|fish|python[0-9.]*|perl|ruby|node)\b",
    r"\b(sh|bash|zsh|python[0-9.]*|perl|ruby|node)\s+-[a-zA-Z]*[ce]\b",
    r"\beval\b",
    # Sending local data somewhere
    r"\bcurl\b.*\s(-d|--data[\w-]*|-F|--form|-T|--upload-file)(\s|=|$)",
    r"\bwget\b.*\s--post-(data|file)\b",
    # Containers and clusters
    r"\bdocker\s+(rm|rmi|system\s+prune|volume\s+(rm|prune))\b",
    r"\bkubectl\s+delete\b",
    r":\(\)\s*\{.*\|.*\}",  # fork bomb
]

COMMAND_TIMEOUT_SECONDS = 120
MAX_FEEDBACK_CHARS = 8000

_SHELL_LANGUAGES = frozenset({"", "bash", "sh", "shell", "zsh"})


def extract_command(response: str) -> str | None:
    """Return the first shell (or untagged) fenced block's content, or None.

    Deliberately never falls back to prose: if the model didn't follow
    CMD_SYSTEM_SUFFIX, running a line of explanation as a command would be worse.
    """
    for language, code in extract_code_blocks(response):
        if language.lower() in _SHELL_LANGUAGES and code.strip():
            return code.strip()
    return None


_QUOTING_RE = re.compile(r"[\\'\"]")


def is_destructive(command: str) -> bool:
    """Return True if the command matches any known destructive pattern."""
    normalized = _QUOTING_RE.sub("", command)
    return any(re.search(pattern, normalized) for pattern in DESTRUCTIVE_PATTERNS)


def log_command(command: str, log_path: Path) -> None:
    """Append a timestamped command to the audit log. Raises StorageError on failure."""
    try:
        ensure_private_dir(log_path.parent)
        timestamp = datetime.now(UTC).isoformat()
        with log_path.open("a") as f:
            f.write(f"[{timestamp}] {command}\n")
        log_path.chmod(0o600)
    except OSError as e:
        raise StorageError(f"Command not logged to {log_path}: {e.strerror or e}") from e


def _shell() -> str | None:
    # Models are told to write bash; /bin/sh is dash on Debian/Ubuntu and lacks
    # brace expansion, [[ ]], <(…) and `source`. Fall back to sh if bash is missing.
    return "/bin/bash" if Path("/bin/bash").exists() else None


def run_command(command: str) -> int:
    """Run a user-confirmed command attached to the terminal. Returns the exit code."""
    result = subprocess.run(command, shell=True, executable=_shell())  # noqa: S602
    return result.returncode


def extract_first_code_block(response: str) -> str | None:
    """Return content of the first fenced code block (any language), or None."""
    blocks = extract_code_blocks(response)
    return blocks[0][1].strip() if blocks else None


def run_command_with_output(
    command: str, timeout: float = COMMAND_TIMEOUT_SECONDS
) -> tuple[str, int]:
    """Run an agent step non-interactively, capturing stdout+stderr. Returns (output, exit_code).

    stdin is /dev/null so prompts (git commit, npm init) fail instead of hanging, the run is
    capped at `timeout` seconds (exit code 124, like timeout(1)), and undecodable bytes are
    replaced rather than crashing.
    """
    try:
        result = subprocess.run(  # noqa: S602
            command,
            shell=True,
            executable=_shell(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        partial = "".join(_as_text(stream) for stream in (e.stdout, e.stderr))
        return f"{partial.strip()}\n[timed out after {timeout:g}s]".strip(), 124
    return (result.stdout + result.stderr).strip(), result.returncode


def _as_text(stream: str | bytes | None) -> str:
    if isinstance(stream, bytes):
        return stream.decode("utf-8", errors="replace")
    return stream or ""


def truncate_for_model(output: str, limit: int = MAX_FEEDBACK_CHARS) -> str:
    """Shorten command output fed back to the model, keeping the start and the end."""
    if len(output) <= limit:
        return output
    half = limit // 2
    omitted = len(output) - 2 * half
    return f"{output[:half]}\n[… {omitted} characters truncated …]\n{output[-half:]}"


class CommandUI(Protocol):
    def confirm(self, prompt: str, exact: str | None = None) -> bool: ...

    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...


def handle_generated_command(
    response: str,
    *,
    dry_run: bool,
    auto_execute: bool,
    can_prompt: bool,
    log_path: Path,
    ui: CommandUI,
) -> None:
    """Extract the command from a --cmd response and run it if allowed.

    Non-destructive commands run straight away with --execute; otherwise the user
    confirms (y/N, or the word "yes" for destructive commands). Without a terminal
    to ask on, nothing runs.
    """
    command = extract_command(response)
    if command is None:
        ui.warning("Could not extract a command from the response.")
        return
    if dry_run:
        ui.info("Dry run — command not executed.")
        return

    destructive = is_destructive(command)
    if not (auto_execute and not destructive):
        if not can_prompt:
            ui.warning(
                "Not executing: stdin is not a terminal, so confirmation can't be asked. "
                "The command was printed above; run it yourself."
            )
            return
        if destructive:
            ui.warning("Destructive command detected — confirmation required.")
            approved = ui.confirm("Type 'yes' to execute: ", exact="yes")
        else:
            approved = ui.confirm("Execute this command? [y/N]: ")
        if not approved:
            return

    # The log is an audit trail, not a safety gate: warn rather than block the command
    try:
        log_command(command, log_path)
    except StorageError as error:
        ui.warning(str(error))
    exit_code = run_command(command)
    if exit_code != 0:
        ui.warning(f"Command exited with code {exit_code}.")
