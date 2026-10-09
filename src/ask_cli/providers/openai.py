"""OpenAI provider — openai SDK."""

from collections.abc import Generator

import openai

from ask_cli.config import ProviderConfig
from ask_cli.providers.base import BaseProvider
from ask_cli.providers.errors import openai_errors


class OpenAIProvider(BaseProvider):
    """Provider for the OpenAI API."""

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

    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        system_prompt: str | None = None,
        think: bool | None = None,  # noqa: ARG002
    ) -> Generator[str, None, None]:
        self.validate()
        client = self._get_client()

        # Inject system prompt as the first message
        all_messages = list(messages)
        if system_prompt:
            all_messages = [{"role": "system", "content": system_prompt}] + all_messages

        token_kwarg = (
            "max_completion_tokens"
            if model.startswith(("gpt-5", "o1", "o3", "o4"))
            else "max_tokens"
        )
        with openai_errors(self.provider_id, self.display_name, model):
            stream = client.chat.completions.create(
                model=model,
                messages=all_messages,  # type: ignore[arg-type]
                stream=True,
                **{token_kwarg: max_tokens},
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is not None and delta.content is not None:
                    yield delta.content
