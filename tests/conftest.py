"""Shared fixtures for ask-cli tests."""

import json
from pathlib import Path

import pytest

from ask_cli.config import (
    AppConfig,
    DefaultsConfig,
    FeaturesConfig,
    OfflineFallbackConfig,
    OutputConfig,
    ProviderConfig,
)


@pytest.fixture
def minimal_provider_config() -> ProviderConfig:
    return ProviderConfig(
        api_key="test-key",
        base_url="https://example.com",
        default_model="test-model",
        fast_model="test-fast-model",
        smart_model="test-smart-model",
    )


@pytest.fixture
def minimal_app_config(minimal_provider_config) -> AppConfig:
    return AppConfig(
        default_provider="zai",
        providers={
            "zai": minimal_provider_config,
            "anthropic": ProviderConfig(api_key="anthropic-key", default_model="claude-3"),
            "openai": ProviderConfig(api_key="openai-key", default_model="gpt-4o"),
            "google": ProviderConfig(api_key="google-key", default_model="gemini-1.5-flash"),
            "ollama": ProviderConfig(base_url="http://localhost:11434", default_model="llama3.2"),
        },
        defaults=DefaultsConfig(max_tokens=4096, quick_max_tokens=256, history_ttl_hours=1),
        features=FeaturesConfig(),
        output=OutputConfig(),
        offline_fallback=OfflineFallbackConfig(),
    )


@pytest.fixture
def config_file(tmp_path) -> Path:
    """Return path to a temp config file with a valid minimal config."""
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "default_provider": "zai",
                "providers": {
                    "zai": {
                        "api_key": "sk-test",
                        "base_url": "https://api.z.ai/v1",
                        "default_model": "claude-sonnet-4-5-20251001",
                        "fast_model": "claude-haiku-4-5-20251001",
                        "smart_model": "claude-opus-4-5-20251001",
                    }
                },
            }
        )
    )
    return path
