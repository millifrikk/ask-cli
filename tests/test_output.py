"""Tests for output helpers — focused on clipboard sanitization."""

import io
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


class TestMarkupEscaping:
    def test_closing_tag_in_error_does_not_crash(self, capsys):
        output.render_error("provider said: bad [/red] tag")
        assert "bad [/red] tag" in capsys.readouterr().err

    def test_square_brackets_in_paths_are_kept(self, capsys):
        output.render_warning("Skipping binary file: app/[slug]/page.tsx")
        assert "app/[slug]/page.tsx" in capsys.readouterr().err

    def test_hint_is_escaped(self, capsys):
        output.render_error("failed", hint="model [default] not found")
        assert "model [default] not found" in capsys.readouterr().err

    def test_info_is_escaped(self, capsys):
        output.render_info("Saved response as '[wip]'.")
        assert "'[wip]'" in capsys.readouterr().err


LONG_LINE = "x" * 200


def _display(mode: str, chunks: list[str]) -> None:
    with output.ResponseDisplay(mode) as display:
        for chunk in chunks:
            display.update(chunk)


class TestResponseDisplayPiped:
    # capsys makes stdout a non-terminal, exactly like `ask ... | jq` or `> file`

    @pytest.mark.parametrize("mode", ["markdown", "raw"])
    def test_emits_source_verbatim_without_wrapping(self, mode, capsys):
        _display(mode, ["# Title\n\n", "- item\n", LONG_LINE])
        assert capsys.readouterr().out == f"# Title\n\n- item\n{LONG_LINE}\n"

    def test_no_double_trailing_newline(self, capsys):
        _display("raw", ["hi\n"])
        assert capsys.readouterr().out == "hi\n"

    def test_empty_response_writes_nothing(self, capsys):
        _display("markdown", [])
        assert capsys.readouterr().out == ""

    def test_json_mode_strips_fence(self, capsys):
        _display("json", ['```json\n{"a": ', "1}\n```"])
        assert capsys.readouterr().out == '{"a": 1}\n'

    def test_json_long_string_survives_round_trip(self, capsys):
        import json

        _display("json", [json.dumps({"text": LONG_LINE})])
        assert json.loads(capsys.readouterr().out) == {"text": LONG_LINE}

    def test_code_mode_prints_only_code(self, capsys):
        _display("code", ["Sure:\n```python\nprint('", LONG_LINE, "')\n```\nDone."])
        assert capsys.readouterr().out == f"print('{LONG_LINE}')\n"

    def test_code_mode_separates_multiple_blocks(self, capsys):
        _display("code", ["```bash\nls\n```\ntext\n```bash\npwd\n```"])
        assert capsys.readouterr().out == "ls\n\npwd\n"

    def test_code_mode_without_blocks_falls_back_to_text(self, capsys):
        _display("code", ["no code here"])
        assert capsys.readouterr().out == "no code here\n"


def test_render_markdown_piped_writes_source_verbatim(capsys):
    output.render_markdown(f"# Saved\n\n{LONG_LINE}")
    assert capsys.readouterr().out == f"# Saved\n\n{LONG_LINE}\n"


class TestResponseDisplayTerminal:
    @pytest.fixture(autouse=True)
    def terminal_console(self):
        output.console = Console(file=io.StringIO(), force_terminal=True, width=80)

    def test_streams_through_live_markdown(self):
        with patch("ask_cli.output.Live") as live_class:
            _display("markdown", ["# Hi"])
        live = live_class.return_value
        rendered = live.update.call_args[0][0]
        assert isinstance(rendered, output.AskMarkdown)

    def test_code_mode_renders_extracted_blocks(self):
        with (
            patch("ask_cli.output.Live"),
            patch("ask_cli.output.render_code") as render_code,
        ):
            _display("code", ["text\n```python\nprint(1)\n```"])
        render_code.assert_called_once_with("print(1)", language="python")


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
