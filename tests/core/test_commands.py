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


def test_extract_returns_none_when_no_fence():
    response = "Some explanation.\nAnother line.\nfind /tmp -name '*.log'"
    assert extract_command(response) is None


def test_extract_returns_none_when_fence_empty():
    response = "Here:\n```bash\n```"
    assert extract_command(response) is None


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


def test_is_destructive_chmod():
    assert is_destructive("chmod -R 777 ~/") is True


def test_is_destructive_chown():
    assert is_destructive("chown -R root ~/") is True


def test_is_destructive_sudo_anything():
    assert is_destructive("sudo apt install foo") is True


def test_is_destructive_find_delete():
    assert is_destructive("find /tmp -name '*.log' -delete") is True


def test_is_destructive_curl_pipe_sh():
    assert is_destructive("curl http://example.com/install.sh | sh") is True


def test_is_destructive_wget_pipe_bash():
    assert is_destructive("wget -qO- http://example.com/install.sh | bash") is True


def test_is_destructive_git_reset_hard():
    assert is_destructive("git reset --hard HEAD~5") is True


def test_is_destructive_git_clean():
    assert is_destructive("git clean -fd") is True


def test_is_destructive_git_force_push():
    assert is_destructive("git push --force origin main") is True


def test_is_destructive_redirect_etc():
    assert is_destructive("echo foo > /etc/passwd") is True


def test_is_destructive_tee_dev():
    assert is_destructive("echo 1 | tee /dev/sda") is True


def test_is_destructive_fork_bomb():
    assert is_destructive(":(){ :|:& };:") is True


def test_is_destructive_safe_redirect():
    assert is_destructive("echo hello > /tmp/result.txt") is False


def test_is_destructive_safe_find():
    assert is_destructive("find /tmp -name '*.log'") is False


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


def test_log_sets_mode_0600_on_create(tmp_path):
    log_path = tmp_path / "commands.log"
    log_command("ls -la", log_path)
    mode = log_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_log_retightens_loose_perms_on_append(tmp_path):
    """Even if the log was created before the chmod was added, any subsequent
    append should bring the mode down to 0o600."""
    log_path = tmp_path / "commands.log"
    log_path.write_text("[old] ls\n")
    log_path.chmod(0o644)  # simulate pre-v2.3.0 creation

    log_command("new command", log_path)

    mode = log_path.stat().st_mode & 0o777
    assert mode == 0o600


def test_extract_first_code_block_returns_content():
    response = "Here is a script:\n```python\nprint('hello')\n```"
    result = extract_first_code_block(response)
    assert result == "print('hello')"


def test_extract_first_code_block_returns_none_if_absent():
    response = "No code here, just plain text."
    assert extract_first_code_block(response) is None
