"""File attachment reading for ask-cli."""

import glob as glob_module
import re
from dataclasses import dataclass, field
from pathlib import Path

from ask_cli.exceptions import AttachmentError

DEFAULT_MAX_FILE_SIZE = 100 * 1024  # 100 KB

_BACKTICK_RUN_RE = re.compile(r"`{3,}")


@dataclass
class Attachments:
    text: str = ""
    warnings: list[str] = field(default_factory=list)


def read_attachments(
    files: list[str],
    patterns: list[str],
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> Attachments:
    """Read file attachments into one context string, plus warnings for the caller to show.

    - Single files must exist and be readable; globs must match at least one file.
    - Oversized files are truncated (only max_file_size bytes are ever read).
    - Binary files are skipped. A file named twice (-f and -F) is included once.
    """
    paths: list[Path] = []

    for name in files:
        path = Path(name)
        if path.is_dir():
            raise AttachmentError(
                f"{name} is a directory, not a file.",
                hint=f"Use -F '{name.rstrip('/')}/**/*' to attach the files inside it.",
            )
        if not path.is_file():
            raise AttachmentError(f"File not found: {name}")
        paths.append(path)

    for pattern in patterns:
        matched = sorted(glob_module.glob(pattern, recursive=True))
        file_matches = [Path(m) for m in matched if Path(m).is_file()]
        if not file_matches:
            raise AttachmentError(f"No files matched pattern: {pattern}")
        paths.extend(file_matches)

    result = Attachments()
    blocks: list[str] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if block := _format_file(path, max_file_size, result.warnings):
            blocks.append(block)
    result.text = "\n\n".join(blocks)
    return result


def _read_prefix(path: Path, limit: int) -> tuple[bytes, int]:
    try:
        with path.open("rb") as file:
            data = file.read(limit + 1)
        return data, path.stat().st_size
    except OSError as e:
        raise AttachmentError(f"Cannot read {path}: {e.strerror or e}") from e


def _decode(data: bytes) -> str | None:
    """Decode UTF-8, tolerating a multibyte character cut off at the end. None if binary."""
    if b"\x00" in data:
        return None
    for cut in range(4):  # a UTF-8 character is at most 4 bytes
        try:
            return data[: len(data) - cut].decode("utf-8")
        except UnicodeDecodeError:
            continue
    return None


def _fence_for(content: str) -> str:
    longest = max((len(run) for run in _BACKTICK_RUN_RE.findall(content)), default=0)
    return "`" * max(3, longest + 1)


def _format_file(path: Path, max_file_size: int, warnings: list[str]) -> str:
    """Read one file and return a formatted context block, or '' for binary files."""
    data, size_bytes = _read_prefix(path, max_file_size)
    truncated = len(data) > max_file_size
    content = _decode(data[:max_file_size])
    if content is None:
        warnings.append(f"Skipping binary file: {path}")
        return ""
    if truncated:
        warnings.append(
            f"{path}: {size_bytes // 1024} KB exceeds {max_file_size // 1024} KB limit — truncating"
        )

    size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"
    header = f"[File: {path} ({size_str})]"
    if truncated:
        header += " [truncated]"
    fence = _fence_for(content)
    language = path.suffix.lstrip(".") or "text"
    return f"{header}\n{fence}{language}\n{content}\n{fence}"
