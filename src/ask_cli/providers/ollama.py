"""Ollama provider — Ollama's OpenAI-compatible endpoint (local or cloud models)."""

import openai

from ask_cli.providers.openai import OpenAIProvider

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(OpenAIProvider):
    """Provider for Ollama via its OpenAI-compatible API; needs no API key."""

    provider_id = "ollama"
    display_name = "Ollama"

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            base_url = self.config.base_url or DEFAULT_BASE_URL
            self._client = openai.OpenAI(api_key="ollama", base_url=f"{base_url.rstrip('/')}/v1")
        return self._client

    def is_configured(self) -> bool:
        # Ollama needs no API key — it just needs to be running
        return True

    def _request_options(self, max_tokens: int, think: bool | None) -> dict:
        options: dict = {"max_tokens": max_tokens}
        # Ollama accepts `think` via extra_body for reasoning models (Qwen3.5,
        # DeepSeek-R1, …); None leaves the model's default.
        if think is not None:
            options["extra_body"] = {"think": think}
        return options

    def _error_hints(self, model: str) -> dict[str, str]:
        return {
            "unreachable_hint": "Is Ollama running? Start it with `ollama serve`.",
            "not_found_hint": f"Download it with `ollama pull {model}`.",
        }
