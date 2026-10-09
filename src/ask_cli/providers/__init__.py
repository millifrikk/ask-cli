"""Provider registry: provider id → BaseProvider subclass."""

from ask_cli.config import AppConfig
from ask_cli.exceptions import ConfigError
from ask_cli.providers.anthropic import AnthropicProvider
from ask_cli.providers.base import BaseProvider
from ask_cli.providers.google import GoogleProvider
from ask_cli.providers.ollama import OllamaProvider
from ask_cli.providers.openai import OpenAIProvider
from ask_cli.providers.zai import ZaiProvider

PROVIDER_CLASSES: dict[str, type[BaseProvider]] = {
    provider.provider_id: provider
    for provider in (ZaiProvider, AnthropicProvider, OpenAIProvider, GoogleProvider, OllamaProvider)
}


def get_provider(name: str, config: AppConfig) -> BaseProvider:
    """Instantiate the named provider from its config section."""
    if name not in PROVIDER_CLASSES:
        raise ConfigError(
            f"Unknown provider '{name}'.",
            hint=f"Available providers: {', '.join(PROVIDER_CLASSES)}",
        )
    provider_config = config.providers.get(name)
    if provider_config is None:
        raise ConfigError(
            f"No configuration found for provider '{name}'.",
            hint=f"Add a providers.{name} section to your config file.",
        )
    return PROVIDER_CLASSES[name](provider_config)


def provider_statuses(config: AppConfig) -> list[tuple[str, str, str]]:
    """(name, "configured" | "not configured", default model) for every provider."""
    rows = []
    for name, provider_class in PROVIDER_CLASSES.items():
        provider_config = config.providers.get(name)
        if provider_config is None:
            rows.append((name, "not configured", ""))
            continue
        configured = provider_class(provider_config).is_configured()
        rows.append(
            (name, "configured" if configured else "not configured", provider_config.default_model)
        )
    return rows
