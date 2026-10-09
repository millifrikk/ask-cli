"""OpenAI provider — Chat Completions API (also the base for Ollama)."""

from collections.abc import Generator

import openai

from ask_cli.config import ProviderConfig
from ask_cli.providers.base import BaseProvider, normalize_stop_reason
from ask_cli.providers.errors import openai_errors


class OpenAIProvider(BaseProvider):
    """Provider for the OpenAI Chat Completions API.

    Subclasses for OpenAI-compatible servers override the client, request options
    and error hints.
    """

    provider_id = "openai"
    display_name = "OpenAI"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: openai.OpenAI | None = None

    def _get_client(self) -> openai.OpenAI:
        if self._client is None:
            self._client = openai.OpenAI(api_key=self.config.api_key)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.config.api_key)

    def _request_options(self, max_tokens: int, think: bool | None) -> dict:  # noqa: ARG002
        # max_tokens is deprecated by OpenAI and rejected by o-series models
        return {"max_completion_tokens": max_tokens}

    def _error_hints(self, model: str) -> dict[str, str]:  # noqa: ARG002
        return {}

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        system_prompt: str | None = None,
        think: bool | None = None,
    ) -> Generator[str, None, None]:
        self.last_stop_reason = None
        self.validate()
        client = self._get_client()

        all_messages = list(messages)
        if system_prompt:
            all_messages = [{"role": "system", "content": system_prompt}, *all_messages]

        with openai_errors(self.provider_id, self.display_name, model, **self._error_hints(model)):
            stream = client.chat.completions.create(
                model=model,
                messages=all_messages,  # type: ignore[arg-type]
                stream=True,
                **self._request_options(max_tokens, think),
            )
            for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue
                if choice.finish_reason:
                    self.last_stop_reason = normalize_stop_reason(choice.finish_reason)
                if choice.delta is not None and choice.delta.content is not None:
                    yield choice.delta.content
