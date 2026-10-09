"""Tests for config loading, env overrides, and model resolution."""

import json
import os
import stat
from unittest.mock import patch

import pytest

from ask_cli.config import (
    AppConfig,
    AppPaths,
    _deep_merge,
    _validate_base_url,
    load_config,
    resolve_model,
    resolve_paths,
)
from ask_cli.exceptions import ConfigError


def _paths(config_dir) -> AppPaths:
    return AppPaths(config_dir=config_dir, data_dir=config_dir / "data")


def test_first_run_creates_config(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(_paths(tmp_path))
    assert config_path.exists()
    assert isinstance(config, AppConfig)


def test_first_run_sets_permissions(tmp_path):
    config_path = tmp_path / "config.json"
    load_config(_paths(tmp_path))
    file_stat = config_path.stat()
    # Owner read+write only
    assert file_stat.st_mode & stat.S_IRUSR
    assert file_stat.st_mode & stat.S_IWUSR
    assert not (file_stat.st_mode & stat.S_IRGRP)
    assert not (file_stat.st_mode & stat.S_IROTH)


def test_load_valid_config(config_file):
    config = load_config(_paths(config_file.parent))
    assert config.default_provider == "zai"
    assert config.providers["zai"].api_key == "sk-test"
    assert config.providers["zai"].default_model == "claude-sonnet-4-5-20251001"


def test_missing_keys_fall_back_to_defaults(tmp_path):
    config_path = tmp_path / "config.json"
    # Only override one thing
    config_path.write_text(json.dumps({"default_provider": "anthropic"}))
    config = load_config(_paths(tmp_path))
    # defaults still present
    assert config.defaults.max_tokens == 4096
    assert config.defaults.quick_max_tokens == 1024


def test_invalid_json_raises_config_error(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ this is not json }")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_config(_paths(tmp_path))


def test_env_var_overrides_api_key(tmp_path, config_file):
    with patch.dict(os.environ, {"ASK_ZAI_API_KEY": "env-override-key"}):
        config = load_config(_paths(config_file.parent))
    assert config.providers["zai"].api_key == "env-override-key"


def test_env_var_anthropic_override(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}))
    with patch.dict(os.environ, {"ASK_ANTHROPIC_API_KEY": "anth-env-key"}):
        config = load_config(_paths(tmp_path))
    assert config.providers["anthropic"].api_key == "anth-env-key"


def test_deep_merge_nested():
    base = {"a": {"x": 1, "y": 2}, "b": 3}
    override = {"a": {"y": 99, "z": 100}, "c": 4}
    result = _deep_merge(base, override)
    assert result["a"]["x"] == 1  # preserved from base
    assert result["a"]["y"] == 99  # overridden
    assert result["a"]["z"] == 100  # added from override
    assert result["b"] == 3  # preserved
    assert result["c"] == 4  # added


def test_deep_merge_non_dict_override():
    base = {"a": {"x": 1}}
    override = {"a": "not-a-dict"}
    result = _deep_merge(base, override)
    assert result["a"] == "not-a-dict"


class TestResolveModel:
    def test_explicit_wins(self, minimal_app_config):
        model = resolve_model(minimal_app_config, "zai", explicit="my-model")
        assert model == "my-model"

    def test_smart_wins_over_fast(self, minimal_app_config):
        model = resolve_model(minimal_app_config, "zai", fast=True, smart=True)
        assert model == "test-smart-model"

    def test_fast_when_not_smart(self, minimal_app_config):
        model = resolve_model(minimal_app_config, "zai", fast=True, smart=False)
        assert model == "test-fast-model"

    def test_default_model(self, minimal_app_config):
        model = resolve_model(minimal_app_config, "zai")
        assert model == "test-model"

    def test_unknown_provider_returns_empty(self, minimal_app_config):
        model = resolve_model(minimal_app_config, "nonexistent")
        assert model == ""


def test_system_prompt_parsed_from_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"defaults": {"system_prompt": "Be terse."}}))
    config = load_config(_paths(tmp_path))
    assert config.defaults.system_prompt == "Be terse."


def test_default_config_includes_linux_system_prompt(tmp_path):
    config = load_config(_paths(tmp_path))  # first run — writes DEFAULT_CONFIG
    assert "Linux" in config.defaults.system_prompt


def test_system_prompt_windows_parsed_from_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"defaults": {"system_prompt_windows": "WIN_TEST"}}))
    config = load_config(_paths(tmp_path))
    assert config.defaults.system_prompt_windows == "WIN_TEST"


def test_default_config_includes_windows_system_prompt(tmp_path):
    config = load_config(_paths(tmp_path))  # creates DEFAULT_CONFIG on first run
    assert "Windows" in config.defaults.system_prompt_windows
    assert "WSL" in config.defaults.system_prompt_windows


def test_base_url_https_no_warning():
    with patch("ask_cli.output.render_warning") as mock_warn:
        _validate_base_url("zai", "https://api.z.ai/api/anthropic")
        mock_warn.assert_not_called()


def test_base_url_localhost_no_warning():
    with patch("ask_cli.output.render_warning") as mock_warn:
        _validate_base_url("ollama", "http://localhost:11434")
        mock_warn.assert_not_called()


def test_base_url_127_no_warning():
    with patch("ask_cli.output.render_warning") as mock_warn:
        _validate_base_url("ollama", "http://127.0.0.1:11434")
        mock_warn.assert_not_called()


def test_base_url_empty_no_warning():
    with patch("ask_cli.output.render_warning") as mock_warn:
        _validate_base_url("anthropic", "")
        mock_warn.assert_not_called()


def test_base_url_plain_http_warns():
    with patch("ask_cli.output.render_warning") as mock_warn:
        _validate_base_url("zai", "http://attacker.example.com/api")
        mock_warn.assert_called_once()


def test_base_url_weird_scheme_warns():
    with patch("ask_cli.output.render_warning") as mock_warn:
        _validate_base_url("zai", "ftp://api.example.com")
        mock_warn.assert_called_once()


class TestMigratePermissions:
    def test_tightens_loose_data_file(self, tmp_path):
        paths = AppPaths(config_dir=tmp_path / "config", data_dir=tmp_path / "data")
        paths.data_dir.mkdir(mode=0o755)
        paths.history_file.write_text("{}")
        paths.history_file.chmod(0o644)

        from ask_cli.config import _migrate_permissions

        _migrate_permissions(paths)

        assert paths.history_file.stat().st_mode & 0o777 == 0o600
        assert paths.data_dir.stat().st_mode & 0o777 == 0o700

    def test_leaves_already_tight_files_alone(self, tmp_path):
        paths = AppPaths(config_dir=tmp_path / "config", data_dir=tmp_path / "data")
        paths.data_dir.mkdir(mode=0o700)
        paths.stats_file.write_text("{}")
        paths.stats_file.chmod(0o600)

        from ask_cli.config import _migrate_permissions

        _migrate_permissions(paths)

        assert paths.stats_file.stat().st_mode & 0o777 == 0o600
        assert paths.data_dir.stat().st_mode & 0o777 == 0o700

    def test_tightens_config_file_at_passed_location(self, tmp_path):
        paths = AppPaths(config_dir=tmp_path / "custom-config", data_dir=tmp_path / "data")
        paths.config_dir.mkdir()
        paths.config_file.write_text("{}")
        paths.config_file.chmod(0o644)

        from ask_cli.config import _migrate_permissions

        _migrate_permissions(paths)

        assert paths.config_file.stat().st_mode & 0o777 == 0o600


class TestResolvePaths:
    def test_honours_xdg_dirs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        paths = resolve_paths()
        assert paths.config_file == tmp_path / "cfg" / "ask" / "config.json"
        assert paths.history_file == tmp_path / "data" / "ask" / "history.json"
        assert paths.stats_file == tmp_path / "data" / "ask" / "stats.json"
        assert paths.saved_dir == tmp_path / "data" / "ask" / "saved"
        assert paths.templates_dir == tmp_path / "data" / "ask" / "templates"
        assert paths.commands_log == tmp_path / "data" / "ask" / "executed_commands.log"

    def test_falls_back_to_home_without_xdg(self, tmp_path, monkeypatch):
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        paths = resolve_paths()
        assert paths.config_file == tmp_path / ".config" / "ask" / "config.json"
        assert paths.history_file == tmp_path / ".local" / "share" / "ask" / "history.json"

    def test_resolved_at_call_time_not_import_time(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "first"))
        first = resolve_paths()
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "second"))
        second = resolve_paths()
        assert first.data_dir != second.data_dir
