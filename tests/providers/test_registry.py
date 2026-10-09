"""Tests for the provider registry."""

import pytest

from ask_cli.config import KNOWN_PROVIDERS, ProviderConfig
from ask_cli.exceptions import ConfigError
from ask_cli.providers import PROVIDER_CLASSES, get_provider, provider_statuses
from ask_cli.providers.anthropic import AnthropicProvider


def test_registry_matches_known_providers():
    assert tuple(PROVIDER_CLASSES) == KNOWN_PROVIDERS


def test_every_provider_class_declares_its_registry_id():
    for name, provider_class in PROVIDER_CLASSES.items():
        assert provider_class.provider_id == name
        assert provider_class.display_name


def test_get_provider_builds_the_configured_class(minimal_app_config):
    provider = get_provider("anthropic", minimal_app_config)
    assert isinstance(provider, AnthropicProvider)
    assert provider.config.api_key == "anthropic-key"


def test_get_provider_rejects_unknown_names(minimal_app_config):
    with pytest.raises(ConfigError, match="Unknown provider") as exc_info:
        get_provider("bogus", minimal_app_config)
    assert "anthropic" in exc_info.value.hint


def test_get_provider_requires_a_config_section(minimal_app_config):
    del minimal_app_config.providers["openai"]
    with pytest.raises(ConfigError, match="No configuration"):
        get_provider("openai", minimal_app_config)


def test_provider_statuses(minimal_app_config):
    minimal_app_config.providers["google"] = ProviderConfig(default_model="gemini")
    statuses = {
        name: (status, model) for name, status, model in provider_statuses(minimal_app_config)
    }
    assert statuses["anthropic"] == ("configured", "claude-3")
    assert statuses["google"] == ("not configured", "gemini")
    assert statuses["ollama"][0] == "configured"
