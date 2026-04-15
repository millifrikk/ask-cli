"""Tests for config loading, env overrides, and model resolution."""

import json
import os
import stat
from unittest.mock import patch

import pytest

from ask_cli.config import (
    AppConfig,
    _deep_merge,
    _validate_base_url,
    load_config,
    resolve_model,
)
from ask_cli.exceptions import ConfigError


def test_first_run_creates_config(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(config_path)
    assert config_path.exists()
    assert isinstance(config, AppConfig)


def test_first_run_sets_permissions(tmp_path):
    config_path = tmp_path / "config.json"
    load_config(config_path)
    file_stat = config_path.stat()
    # Owner read+write only
    assert file_stat.st_mode & stat.S_IRUSR
    assert file_stat.st_mode & stat.S_IWUSR
    assert not (file_stat.st_mode & stat.S_IRGRP)
    assert not (file_stat.st_mode & stat.S_IROTH)


def test_load_valid_config(config_file):
    config = load_config(config_file)
    assert config.default_provider == "zai"
    assert config.providers["zai"].api_key == "sk-test"
    assert config.providers["zai"].default_model == "claude-sonnet-4-5-20251001"


def test_missing_keys_fall_back_to_defaults(tmp_path):
    config_path = tmp_path / "config.json"
    # Only override one thing
    config_path.write_text(json.dumps({"default_provider": "anthropic"}))
    config = load_config(config_path)
    # defaults still present
    assert config.defaults.max_tokens == 4096
    assert config.defaults.quick_max_tokens == 1024


def test_invalid_json_raises_config_error(tmp_path):
    config_path = tmp_path / "bad.json"
    config_path.write_text("{ this is not json }")
    with pytest.raises(ConfigError, match="Invalid JSON"):
        load_config(config_path)


def test_env_var_overrides_api_key(tmp_path, config_file):
    with patch.dict(os.environ, {"ASK_ZAI_API_KEY": "env-override-key"}):
        config = load_config(config_file)
    assert config.providers["zai"].api_key == "env-override-key"


def test_env_var_anthropic_override(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}))
    with patch.dict(os.environ, {"ASK_ANTHROPIC_API_KEY": "anth-env-key"}):
        config = load_config(config_path)
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
    config = load_config(config_path)
    assert config.defaults.system_prompt == "Be terse."


def test_default_config_includes_linux_system_prompt(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(config_path)  # first run — writes DEFAULT_CONFIG
    assert "Linux" in config.defaults.system_prompt


def test_system_prompt_windows_parsed_from_config(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"defaults": {"system_prompt_windows": "WIN_TEST"}}))
    config = load_config(config_path)
    assert config.defaults.system_prompt_windows == "WIN_TEST"


def test_default_config_includes_windows_system_prompt(tmp_path):
    config_path = tmp_path / "config.json"
    config = load_config(config_path)  # creates DEFAULT_CONFIG on first run
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
    def test_tightens_loose_data_file(self, tmp_path, monkeypatch):
        fake_data = tmp_path / "data"
        fake_data.mkdir(mode=0o755)
        fake_hist = fake_data / "history.json"
        fake_hist.write_text("{}")
        fake_hist.chmod(0o644)

        monkeypatch.setattr("ask_cli.config._data_dir", lambda: fake_data)
        monkeypatch.setattr("ask_cli.config.HISTORY_PATH", fake_hist)
        monkeypatch.setattr("ask_cli.config.COMMANDS_LOG_PATH", fake_data / "missing.log")
        monkeypatch.setattr("ask_cli.config.USAGE_STATS_PATH", fake_data / "missing.json")
        monkeypatch.setattr("ask_cli.config.SAVED_DIR", fake_data / "saved-missing")
        monkeypatch.setattr("ask_cli.config.TEMPLATES_DIR", fake_data / "templates-missing")
        monkeypatch.setattr("ask_cli.config.CONFIG_PATH", fake_data / "config-missing.json")
        monkeypatch.setattr("ask_cli.config._config_dir", lambda: fake_data / "config-missing-dir")

        from ask_cli.config import _migrate_permissions

        _migrate_permissions()

        assert fake_hist.stat().st_mode & 0o777 == 0o600
        assert fake_data.stat().st_mode & 0o777 == 0o700

    def test_leaves_already_tight_files_alone(self, tmp_path, monkeypatch):
        fake_data = tmp_path / "data"
        fake_data.mkdir(mode=0o700)
        fake_stats = fake_data / "stats.json"
        fake_stats.write_text("{}")
        fake_stats.chmod(0o600)

        monkeypatch.setattr("ask_cli.config._data_dir", lambda: fake_data)
        monkeypatch.setattr("ask_cli.config.USAGE_STATS_PATH", fake_stats)
        monkeypatch.setattr("ask_cli.config.HISTORY_PATH", fake_data / "h-missing.json")
        monkeypatch.setattr("ask_cli.config.COMMANDS_LOG_PATH", fake_data / "log-missing.log")
        monkeypatch.setattr("ask_cli.config.SAVED_DIR", fake_data / "saved-missing")
        monkeypatch.setattr("ask_cli.config.TEMPLATES_DIR", fake_data / "templates-missing")
        monkeypatch.setattr("ask_cli.config.CONFIG_PATH", fake_data / "config-missing.json")
        monkeypatch.setattr("ask_cli.config._config_dir", lambda: fake_data / "config-missing-dir")

        from ask_cli.config import _migrate_permissions

        _migrate_permissions()

        assert fake_stats.stat().st_mode & 0o777 == 0o600
        assert fake_data.stat().st_mode & 0o777 == 0o700
