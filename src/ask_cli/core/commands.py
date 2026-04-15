"""Shell command extraction, safety checks, and execution for ask-cli."""

import re
import subprocess
from pathlib import Path

CMD_SYSTEM_SUFFIX = (
    "Return ONLY a single executable shell command in a fenced code block (```bash ... ```). "
    "Do not include explanations. If multiple steps are needed, chain them with && or ||."
)

DESTRUCTIVE_PATTERNS = [
    r"\brm\b",
    r"\bdd\b",
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bkill\b",
    r"\bkillall\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\btruncate\b",
    r"\bwipe\b",
    r"\bchmod\b",
    r"\bchown\b",
    r"\bchattr\b",
    r"\bsudo\b",
    r"\bdoas\b",
    r"\bfind\b.*\s-delete\b",
    r"\bfind\b.*\s-exec\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b",
    r"\bgit\s+push\b.*--force\b",
    r"\bgit\s+push\b.*-f\b",
    r"\b(curl|wget|fetch)\b[^|]*\|\s*(sh|bash|zsh|fish)\b",
    r"\btee\b\s+(-a\s+)?/(etc|boot|usr|bin|sbin|dev)\b",
    r">>?\s*/(etc|boot|usr|bin|sbin|dev)\b",
    r":\(\)\s*\{.*\|.*\}",  # fork bomb
]

_FENCE_RE = re.compile(r"```(?:bash|sh|shell)?\n(.*?)```", re.DOTALL)
_ANY_FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


def extract_command(response: str) -> str | None:
    """Extract the first shell command from a fenced code block.

    Returns None if no fenced block is present — previously this fell back to
    the last non-empty line, which could turn explanatory prose into a shell
    command when the model didn't follow the CMD_SYSTEM_SUFFIX directive.
    """
    if not response or not response.strip():
        return None

    match = _FENCE_RE.search(response)
    if match:
        command = match.group(1).strip()
        return command if command else None

    return None


def is_destructive(command: str) -> bool:
    """Return True if the command matches any known destructive pattern."""
    return any(re.search(pattern, command) for pattern in DESTRUCTIVE_PATTERNS)


def log_command(command: str, log_path: Path) -> None:
    """Append a timestamped command to the log file. Silent on OSError."""
    from datetime import UTC, datetime

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).isoformat()
        with log_path.open("a") as f:
            f.write(f"[{timestamp}] {command}\n")
        log_path.chmod(0o600)
    except OSError:
        pass


def run_command(command: str) -> int:
    """Run command via shell. Returns the exit code."""
    result = subprocess.run(command, shell=True)  # noqa: S602
    return result.returncode


def extract_first_code_block(response: str) -> str | None:
    """Return content of the first fenced code block (any language), or None."""
    match = _ANY_FENCE_RE.search(response)
    return match.group(1).strip() if match else None


def run_command_with_output(command: str) -> tuple[str, int]:
    """Run command via shell, capturing combined stdout+stderr. Returns (output, exit_code)."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)  # noqa: S602
    return (result.stdout + result.stderr).strip(), result.returncode
