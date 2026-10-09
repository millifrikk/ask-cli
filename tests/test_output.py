"""Tests for output helpers — focused on clipboard sanitization."""

import re
from pathlib import Path
from unittest.mock import patch

import pyperclip
import pytest
from rich.console import Console

from ask_cli import output
from ask_cli.output import _sanitize_for_clipboard, copy_to_clipboard

SRC_DIR = Path(__file__).resolve().parent.parent / "src" / "ask_cli"


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


class TestDiagnosticsGoToStderr:
    @pytest.mark.parametrize(
        "render", [output.render_error, output.render_warning, output.render_info]
    )
    def test_diagnostics_never_touch_stdout(self, render, capsys):
        render("something happened")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "something happened" in captured.err

    def test_clipboard_notice_goes_to_stderr(self, capsys):
        copy_to_clipboard("echo hi", "Code")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "copied to clipboard" in captured.err


class TestDisableColor:
    def test_errors_have_no_ansi_and_no_literal_markup(self, monkeypatch, capsys):
        # Simulate a colour terminal so the test fails if colour survives --no-color
        monkeypatch.setenv("FORCE_COLOR", "1")
        output.err_console = Console(stderr=True, force_terminal=True)
        output.render_error("before")
        assert "\x1b" in capsys.readouterr().err
        output.disable_color()
        output.render_error("boom", hint="try again")
        err = capsys.readouterr().err
        assert "Error:" in err
        assert "boom" in err
        assert "\x1b" not in err
        assert "[bold red]" not in err
        assert "[dim]" not in err

    def test_stdout_console_has_no_color_system(self, monkeypatch):
        monkeypatch.setenv("FORCE_COLOR", "1")
        output.disable_color()
        assert output.console.color_system is None
        assert output.err_console.color_system is None

    def test_no_module_binds_console_at_import_time(self):
        # disable_color() rebinds output.console; a `from ask_cli.output import console`
        # elsewhere would keep the old, coloured instance.
        pattern = re.compile(r"from ask_cli\.output import \(?[^)]*\b(err_)?console\b", re.S)
        offenders = [
            str(path.relative_to(SRC_DIR))
            for path in SRC_DIR.rglob("*.py")
            if path.name != "output.py" and pattern.search(path.read_text())
        ]
        assert offenders == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
