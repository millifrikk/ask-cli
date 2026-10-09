"""Z.ai provider — Anthropic SDK pointed at the Z.ai base URL."""

from collections.abc import Generator

import anthropic

from ask_cli.config import ProviderConfig
from ask_cli.providers.base import BaseProvider, normalize_stop_reason
from ask_cli.providers.errors import anthropic_errors


class ZaiProvider(BaseProvider):
    """Provider for Z.ai (Anthropic-compatible API at a custom base URL)."""

    provider_id = "zai"
    display_name = "Z.ai"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            kwargs: dict = {"api_key": self.config.api_key}
            if self.config.base_url:
                kwargs["base_url"] = self.config.base_url
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def is_configured(self) -> bool:
        return bool(self.config.api_key)

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        system_prompt: str | None = None,
        think: bool | None = None,  # noqa: ARG002
    ) -> Generator[str, None, None]:
        self.last_stop_reason = None
        self.validate()
        client = self._get_client()

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        with (
            anthropic_errors(self.provider_id, self.display_name, model),
            client.messages.stream(**kwargs) as stream,
        ):
            yield from stream.text_stream
            self.last_stop_reason = normalize_stop_reason(stream.get_final_message().stop_reason)
