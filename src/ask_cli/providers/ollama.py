"""Ollama provider — OpenAI-compatible SDK pointed at localhost."""

from collections.abc import Generator

import openai

from ask_cli.config import ProviderConfig
from ask_cli.providers.base import BaseProvider, normalize_stop_reason
from ask_cli.providers.errors import openai_errors


class OllamaProvider(BaseProvider):
    """Provider for Ollama running locally (OpenAI-compatible API)."""

    provider_id = "ollama"
    display_name = "Ollama"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: openai.OpenAI | None = None

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            base_url = self.config.base_url or "http://localhost:11434"
            self._client = openai.OpenAI(
                api_key="ollama",
                base_url=f"{base_url.rstrip('/')}/v1",
            )
        return self._client

    def is_configured(self) -> bool:
        # Ollama needs no API key — it just needs to be running
        return True

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        system_prompt: str | None = None,
        think: bool | None = None,
    ) -> Generator[str, None, None]:
        self.last_stop_reason = None
        client = self._get_client()

        all_messages = list(messages)
        if system_prompt:
            all_messages = [{"role": "system", "content": system_prompt}] + all_messages

        # Ollama's OpenAI-compat endpoint accepts `think` via extra_body for
        # reasoning models (Qwen3.5, DeepSeek-R1, …). Passing None skips it.
        extra_body = {"think": think} if think is not None else None

        with openai_errors(
            self.provider_id,
            self.display_name,
            model,
            unreachable_hint="Is Ollama running? Start it with `ollama serve`.",
            not_found_hint=f"Download it with `ollama pull {model}`.",
        ):
            stream = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=all_messages,  # type: ignore[arg-type]
                stream=True,
                extra_body=extra_body,
            )
            for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue
                if choice.finish_reason:
                    self.last_stop_reason = normalize_stop_reason(choice.finish_reason)
                if choice.delta is not None and choice.delta.content is not None:
                    yield choice.delta.content
