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
    api_key_env_var,
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


class TestDefaultConfigImmutability:
    def test_load_config_does_not_mutate_default_config(self, tmp_path, monkeypatch):
        import copy

        from ask_cli.config import DEFAULT_CONFIG

        snapshot = copy.deepcopy(DEFAULT_CONFIG)
        monkeypatch.setenv("ASK_ANTHROPIC_API_KEY", "env-secret")
        (tmp_path / "config.json").write_text("{}")
        load_config(_paths(tmp_path))
        assert snapshot == DEFAULT_CONFIG

    def test_first_run_file_never_contains_env_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ASK_ANTHROPIC_API_KEY", "env-secret")
        monkeypatch.setenv("ASK_OPENAI_API_KEY", "env-secret-2")
        # A prior load in the same process used to poison DEFAULT_CONFIG
        load_config(_paths(tmp_path / "first"))
        load_config(_paths(tmp_path / "second"))
        for run in ("first", "second"):
            written = (tmp_path / run / "config.json").read_text()
            assert "env-secret" not in written


def test_api_key_env_var_naming():
    assert api_key_env_var("anthropic") == "ASK_ANTHROPIC_API_KEY"
    assert api_key_env_var("zai") == "ASK_ZAI_API_KEY"


def test_invalid_json_hint_warns_against_deleting(tmp_path):
    (tmp_path / "config.json").write_text("{ nope")
    with pytest.raises(ConfigError) as exc_info:
        load_config(_paths(tmp_path))
    hint = exc_info.value.hint
    assert hint is not None
    assert "API keys" in hint
    assert str(tmp_path / "config.json") in str(exc_info.value)


@pytest.mark.parametrize(
    ("content", "key_path"),
    [
        ([], "top level"),
        ("x", "top level"),
        ({"providers": None}, "providers"),
        ({"providers": {"zai": None}}, "providers.zai"),
        ({"providers": {"zai": {"api_key": 123}}}, "providers.zai.api_key"),
        ({"defaults": None}, "defaults"),
        ({"defaults": {"max_tokens": "4096"}}, "defaults.max_tokens"),
        ({"defaults": {"max_tokens": 0}}, "defaults.max_tokens"),
        ({"defaults": {"history_ttl_hours": True}}, "defaults.history_ttl_hours"),
        ({"default_provider": 5}, "default_provider"),
        ({"features": {"clipboard": "yes"}}, "features.clipboard"),
        ({"output": {"code_theme": None}}, "output.code_theme"),
    ],
)
def test_wrong_shapes_raise_config_error_naming_the_key(tmp_path, content, key_path):
    (tmp_path / "config.json").write_text(json.dumps(content))
    with pytest.raises(ConfigError) as exc_info:
        load_config(_paths(tmp_path))
    assert key_path in str(exc_info.value)
    assert str(tmp_path / "config.json") in str(exc_info.value)


def test_non_utf8_config_raises_config_error(tmp_path):
    (tmp_path / "config.json").write_bytes(b"\xff\xfe")
    with pytest.raises(ConfigError):
        load_config(_paths(tmp_path))


def test_unknown_keys_are_tolerated(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps({"legacy_option": 1, "providers": {}}))
    assert load_config(_paths(tmp_path)).default_provider == "ollama"


def test_set_default_provider_writes_privately_and_keeps_other_keys(tmp_path):
    from ask_cli.config import set_default_provider

    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"default_provider": "zai", "providers": {"zai": {}}}))
    config_path.chmod(0o644)
    set_default_provider(config_path, "anthropic")
    saved = json.loads(config_path.read_text())
    assert saved == {"default_provider": "anthropic", "providers": {"zai": {}}}
    assert config_path.stat().st_mode & 0o777 == 0o600


def test_set_default_provider_rejects_unknown_provider(tmp_path):
    from ask_cli.config import set_default_provider

    with pytest.raises(ConfigError, match="Unknown provider"):
        set_default_provider(tmp_path / "config.json", "bogus")


def test_set_default_provider_refuses_to_clobber_corrupt_config(tmp_path):
    from ask_cli.config import set_default_provider

    config_path = tmp_path / "config.json"
    config_path.write_text("{ broken")
    with pytest.raises(ConfigError):
        set_default_provider(config_path, "anthropic")
    assert config_path.read_text() == "{ broken"
