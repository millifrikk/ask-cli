"""File attachment reading for ask-cli."""

import glob as glob_module
from pathlib import Path

from ask_cli.exceptions import AttachmentError
from ask_cli.output import render_warning

DEFAULT_MAX_FILE_SIZE = 100 * 1024  # 100 KB


def read_attachments(
    files: list[str],
    patterns: list[str],
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
) -> str:
    """Read file attachments and return a formatted context string.

    - Single files: must exist; raises AttachmentError if not found.
    - Glob patterns: raises AttachmentError if nothing matches.
    - Oversized files: warned and truncated (not rejected).
    - Binary files: warned and skipped.
    - Returns empty string when both lists are empty.
    """
    paths: list[Path] = []

    for f in files:
        p = Path(f)
        if not p.exists() or not p.is_file():
            raise AttachmentError(f"File not found: {f}")
        paths.append(p)

    for pattern in patterns:
        matched = sorted(glob_module.glob(pattern, recursive=True))
        file_matches = [Path(m) for m in matched if Path(m).is_file()]
        if not file_matches:
            raise AttachmentError(f"No files matched pattern: {pattern}")
        paths.extend(file_matches)

    if not paths:
        return ""

    parts = [block for p in paths if (block := _format_file(p, max_file_size))]
    return "\n\n".join(parts)


def _format_file(path: Path, max_file_size: int) -> str:
    """Read one file and return a formatted context block, or '' for binary files."""
    size_bytes = path.stat().st_size
    ext = path.suffix.lstrip(".") or "text"

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        render_warning(f"Skipping binary file: {path.name}")
        return ""

    truncated = False
    if len(content.encode("utf-8")) > max_file_size:
        kb_actual = size_bytes // 1024
        kb_limit = max_file_size // 1024
        render_warning(f"{path.name}: {kb_actual} KB exceeds {kb_limit} KB limit — truncating")
        content = content.encode("utf-8")[:max_file_size].decode("utf-8", errors="ignore")
        truncated = True

    size_str = f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"
    header = f"[File: {path.name} ({size_str})]"
    if truncated:
        header += " [truncated]"

    return f"{header}\n```{ext}\n{content}\n```"
