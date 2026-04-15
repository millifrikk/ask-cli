"""Tests for output helpers — focused on clipboard sanitization."""

from unittest.mock import patch

import pyperclip
import pytest

from ask_cli.output import _sanitize_for_clipboard, copy_to_clipboard


class TestSanitizeForClipboard:
    def test_strips_trailing_newline(self):
        assert _sanitize_for_clipboard("echo hi\n") == "echo hi"

    def test_strips_multiple_trailing_newlines(self):
        assert _sanitize_for_clipboard("echo hi\n\n\n") == "echo hi"

    def test_strips_carriage_returns_anywhere(self):
        assert _sanitize_for_clipboard("echo hi\rrm -rf /") == "echo hirm -rf /"

    def test_preserves_internal_newlines(self):
        assert _sanitize_for_clipboard("line1\nline2\nline3") == "line1\nline2\nline3"

    def test_preserves_leading_whitespace(self):
        assert _sanitize_for_clipboard("   indented\n") == "   indented"

    def test_empty_input(self):
        assert _sanitize_for_clipboard("") == ""


class TestCopyToClipboard:
    def test_copies_sanitized_content(self):
        with patch("ask_cli.output.pyperclip.copy") as mock_copy:
            copy_to_clipboard("echo hi\n", "Code")
            mock_copy.assert_called_once_with("echo hi")

    def test_renders_info_on_success(self):
        with (
            patch("ask_cli.output.pyperclip.copy"),
            patch("ask_cli.output.render_info") as mock_info,
        ):
            copy_to_clipboard("hello", "Response")
            mock_info.assert_called_once()
            assert "Response" in mock_info.call_args[0][0]

    def test_renders_warning_when_clipboard_unavailable(self):
        err = pyperclip.PyperclipException("no clipboard")
        with (
            patch("ask_cli.output.pyperclip.copy", side_effect=err),
            patch("ask_cli.output.render_warning") as mock_warn,
        ):
            copy_to_clipboard("hello", "Response")
            mock_warn.assert_called_once()

    def test_pastejacking_trailing_newline_stripped(self):
        """The critical case: a command with trailing newline must not auto-execute on paste."""
        malicious = "echo safe\nrm -rf ~/\n"
        with patch("ask_cli.output.pyperclip.copy") as mock_copy:
            copy_to_clipboard(malicious, "Code")
            copied = mock_copy.call_args[0][0]
            assert not copied.endswith("\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
