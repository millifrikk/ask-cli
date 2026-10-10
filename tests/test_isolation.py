"""Guards proving the test suite never touches the real user environment."""

import os

import pyperclip

from ask_cli.config import resolve_paths


def test_api_key_env_vars_are_cleared():
    assert not [name for name in os.environ if name.startswith("ASK_")]


def test_resolved_paths_live_under_tmp_path(tmp_path):
    paths = resolve_paths()
    assert paths.config_dir.is_relative_to(tmp_path)
    assert paths.data_dir.is_relative_to(tmp_path)


def test_home_is_redirected(tmp_path):
    assert os.path.expanduser("~") == str(tmp_path / "home")


def test_clipboard_is_stubbed(fake_clipboard):
    pyperclip.copy("hello")
    assert fake_clipboard == ["hello"]
    assert pyperclip.paste() == "hello"
