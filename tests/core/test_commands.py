"""Tests for shell command extraction, safety checks, and logging."""

from unittest.mock import patch

from ask_cli.core.commands import (
    extract_command,
    extract_first_code_block,
    is_destructive,
    log_command,
)


def test_extract_from_bash_fence():
    response = "Here you go:\n```bash\nls -la\n```"
    assert extract_command(response) == "ls -la"


def test_extract_from_bare_fence():
    response = "```\necho hello\n```"
    assert extract_command(response) == "echo hello"


def test_extract_from_sh_fence():
    response = "```sh\ndf -h\n```"
    assert extract_command(response) == "df -h"


def test_extract_fallback_last_line():
    response = "Some explanation.\nAnother line.\nfind /tmp -name '*.log'"
    assert extract_command(response) == "find /tmp -name '*.log'"


def test_extract_empty_returns_none():
    assert extract_command("") is None
    assert extract_command("   ") is None


def test_is_destructive_rm():
    assert is_destructive("rm -rf /tmp/old") is True


def test_is_destructive_safe():
    assert is_destructive("ls -la /tmp") is False


def test_is_destructive_sudo_rm():
    assert is_destructive("sudo rm -rf /") is True


def test_is_destructive_kill():
    assert is_destructive("kill -9 1234") is True


def test_log_writes_to_file(tmp_path):
    log_path = tmp_path / "commands.log"
    log_command("ls -la", log_path)
    content = log_path.read_text()
    assert "ls -la" in content


def test_log_creates_parent_dir(tmp_path):
    log_path = tmp_path / "nested" / "dir" / "commands.log"
    log_command("echo hi", log_path)
    assert log_path.exists()


def test_log_silent_on_oserror(tmp_path):
    log_path = tmp_path / "commands.log"
    with patch("builtins.open", side_effect=OSError("disk full")):
        # Must not raise
        log_command("ls", log_path)


def test_extract_first_code_block_returns_content():
    response = "Here is a script:\n```python\nprint('hello')\n```"
    result = extract_first_code_block(response)
    assert result == "print('hello')"


def test_extract_first_code_block_returns_none_if_absent():
    response = "No code here, just plain text."
    assert extract_first_code_block(response) is None
