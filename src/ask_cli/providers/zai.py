"""Z.ai provider — the Anthropic-compatible API at Z.ai's base URL."""

from ask_cli.providers.anthropic import AnthropicProvider


class ZaiProvider(AnthropicProvider):
    """Z.ai speaks the Anthropic Messages API; base_url comes from config."""

    provider_id = "zai"
    display_name = "Z.ai"
