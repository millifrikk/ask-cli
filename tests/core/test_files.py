"""Tests for file attachment reading logic."""

import os
from unittest.mock import patch

import pytest

from ask_cli.core.files import read_attachments
from ask_cli.exceptions import AttachmentError


def test_no_files_returns_empty():
    result = read_attachments([], [])
    assert (result.text, result.warnings) == ("", [])


def test_single_file_content_included(tmp_path):
    f = tmp_path / "hello.py"
    f.write_text("print('hello')")
    text = read_attachments([str(f)], []).text
    assert "hello.py" in text
    assert "print('hello')" in text


def test_file_not_found_raises():
    with pytest.raises(AttachmentError, match="File not found"):
        read_attachments(["/nonexistent/path/file.txt"], [])


def test_directory_gets_its_own_message_and_hint(tmp_path):
    with pytest.raises(AttachmentError, match="is a directory") as exc_info:
        read_attachments([str(tmp_path)], [])
    assert "-F" in exc_info.value.hint


@pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
def test_unreadable_file_raises_attachment_error(tmp_path):
    f = tmp_path / "secret.txt"
    f.write_text("nope")
    f.chmod(0o000)
    with pytest.raises(AttachmentError, match="Cannot read"):
        read_attachments([str(f)], [])


def test_glob_pattern_matches(tmp_path):
    (tmp_path / "a.py").write_text("# a")
    (tmp_path / "b.py").write_text("# b")
    text = read_attachments([], [str(tmp_path / "*.py")]).text
    assert "a.py" in text
    assert "b.py" in text


def test_glob_no_match_raises(tmp_path):
    with pytest.raises(AttachmentError, match="No files matched pattern"):
        read_attachments([], [str(tmp_path / "*.xyz")])


def test_oversized_file_truncated_with_warning(tmp_path):
    f = tmp_path / "big.txt"
    f.write_text("x" * 5000)
    result = read_attachments([str(f)], [], max_file_size=1024)
    assert "[truncated]" in result.text
    assert "x" * 1024 in result.text
    assert "x" * 1025 not in result.text
    assert any("truncating" in warning for warning in result.warnings)


def test_large_file_is_not_read_whole(tmp_path):
    f = tmp_path / "huge.log"
    f.write_text("y" * 200_000)
    with (
        patch("pathlib.Path.read_text", side_effect=AssertionError("read whole file")),
        patch("pathlib.Path.read_bytes", side_effect=AssertionError("read whole file")),
    ):
        result = read_attachments([str(f)], [], max_file_size=1024)
    assert "[truncated]" in result.text


def test_truncation_never_splits_a_multibyte_character(tmp_path):
    f = tmp_path / "unicode.txt"
    f.write_text("é" * 100)  # 2 bytes each
    text = read_attachments([str(f)], [], max_file_size=51).text
    assert "é" * 25 in text
    assert "�" not in text


def test_binary_file_skipped_with_warning(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(bytes(range(256)))
    result = read_attachments([str(f)], [])
    assert result.text == ""
    assert any("binary" in warning for warning in result.warnings)


def test_warnings_are_returned_not_printed(tmp_path, capsys):
    f = tmp_path / "data.bin"
    f.write_bytes(b"\x00\x01")
    read_attachments([str(f)], [])
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", "")


def test_multiple_files_joined(tmp_path):
    (tmp_path / "first.txt").write_text("content one")
    (tmp_path / "second.txt").write_text("content two")
    text = read_attachments([str(tmp_path / "first.txt"), str(tmp_path / "second.txt")], []).text
    assert "\n\n" in text
    assert "first.txt" in text
    assert "second.txt" in text


def test_same_file_via_file_and_glob_is_included_once(tmp_path):
    f = tmp_path / "once.py"
    f.write_text("unique_marker = 1")
    text = read_attachments([str(f)], [str(tmp_path / "*.py")]).text
    assert text.count("unique_marker") == 1


def test_files_with_same_name_are_labelled_by_path(tmp_path):
    for package in ("alpha", "beta"):
        (tmp_path / package).mkdir()
        (tmp_path / package / "__init__.py").write_text(f"# {package}")
    text = read_attachments([], [str(tmp_path / "**" / "__init__.py")]).text
    assert f"{tmp_path / 'alpha' / '__init__.py'}" in text
    assert f"{tmp_path / 'beta' / '__init__.py'}" in text


def test_content_containing_fences_gets_a_longer_fence(tmp_path):
    f = tmp_path / "README.md"
    f.write_text("Example:\n```bash\nls\n```\n")
    text = read_attachments([str(f)], []).text
    assert "\n````md\n" in text
    assert text.endswith("\n````")


def test_size_shown_in_bytes_and_kb(tmp_path):
    (tmp_path / "small.txt").write_text("hi")
    (tmp_path / "bigger.txt").write_text("x" * 2048)
    assert " B)" in read_attachments([str(tmp_path / "small.txt")], []).text
    assert " KB)" in read_attachments([str(tmp_path / "bigger.txt")], []).text


def test_fence_language_from_extension_or_text(tmp_path):
    (tmp_path / "script.py").write_text("pass")
    (tmp_path / "Makefile").write_text("all:")
    assert "```py\n" in read_attachments([str(tmp_path / "script.py")], []).text
    assert "```text\n" in read_attachments([str(tmp_path / "Makefile")], []).text
