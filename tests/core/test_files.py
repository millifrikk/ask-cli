"""Tests for file attachment reading logic."""

from unittest.mock import patch

import pytest

from ask_cli.core.files import DEFAULT_MAX_FILE_SIZE, _format_file, read_attachments
from ask_cli.exceptions import AttachmentError


def test_no_files_returns_empty():
    assert read_attachments([], []) == ""


def test_single_file_content_included(tmp_path):
    f = tmp_path / "hello.py"
    f.write_text("print('hello')")
    result = read_attachments([str(f)], [])
    assert "hello.py" in result
    assert "print('hello')" in result


def test_file_not_found_raises():
    with pytest.raises(AttachmentError, match="File not found"):
        read_attachments(["/nonexistent/path/file.txt"], [])


def test_directory_path_raises(tmp_path):
    with pytest.raises(AttachmentError, match="File not found"):
        read_attachments([str(tmp_path)], [])


def test_glob_pattern_matches(tmp_path):
    (tmp_path / "a.py").write_text("# a")
    (tmp_path / "b.py").write_text("# b")
    result = read_attachments([], [str(tmp_path / "*.py")])
    assert "a.py" in result
    assert "b.py" in result


def test_glob_no_match_raises(tmp_path):
    with pytest.raises(AttachmentError, match="No files matched pattern"):
        read_attachments([], [str(tmp_path / "*.xyz")])


def test_oversized_file_truncated(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 200)
    with patch("ask_cli.core.files.render_warning"):
        result = read_attachments([str(f)], [], max_file_size=100)
    assert "[truncated]" in result
    # Content should be cut to 100 bytes worth
    assert len(result) < 200 + 200  # much less than the original 200 chars plus header overhead


def test_binary_file_skipped(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(bytes(range(256)))
    with patch("ask_cli.core.files.render_warning"):
        result = read_attachments([str(f)], [])
    assert result == ""


def test_multiple_files_joined(tmp_path):
    (tmp_path / "first.txt").write_text("content one")
    (tmp_path / "second.txt").write_text("content two")
    result = read_attachments([str(tmp_path / "first.txt"), str(tmp_path / "second.txt")], [])
    # The two blocks should be separated by a blank line
    assert "\n\n" in result
    assert "first.txt" in result
    assert "second.txt" in result


def test_format_includes_size_bytes(tmp_path):
    f = tmp_path / "small.txt"
    f.write_text("hi")
    result = _format_file(f, DEFAULT_MAX_FILE_SIZE)
    assert " B)" in result


def test_format_includes_size_kb(tmp_path):
    f = tmp_path / "bigger.txt"
    f.write_text("x" * 1024)
    result = _format_file(f, DEFAULT_MAX_FILE_SIZE)
    assert " KB)" in result


def test_format_uses_extension_as_language(tmp_path):
    f = tmp_path / "script.py"
    f.write_text("pass")
    result = _format_file(f, DEFAULT_MAX_FILE_SIZE)
    assert "```py" in result


def test_format_no_extension_uses_text(tmp_path):
    f = tmp_path / "Makefile"
    f.write_text("all:")
    result = _format_file(f, DEFAULT_MAX_FILE_SIZE)
    assert "```text" in result
