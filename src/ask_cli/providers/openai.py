"""OpenAI provider — openai SDK."""

from collections.abc import Generator

import openai

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ModelNotFoundError, ProviderError
from ask_cli.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """Provider for the OpenAI API."""

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
    ) -> Generator[str, None, None]:
        self.validate()
        client = self._get_client()

        # Inject system prompt as the first message
        all_messages = list(messages)
        if system_prompt:
            all_messages = [{"role": "system", "content": system_prompt}] + all_messages

        # TODO: o1 models don't support system messages and use max_completion_tokens instead
        try:
            stream = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=all_messages,  # type: ignore[arg-type]
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is not None and delta.content is not None:
                    yield delta.content
        except openai.AuthenticationError as e:
            raise ProviderError(
                "Authentication failed — check your OpenAI API key.",
                provider="openai",
                status_code=401,
            ) from e
        except openai.RateLimitError as e:
            raise ProviderError(
                "Rate limit exceeded — slow down requests or upgrade your plan.",
                provider="openai",
                status_code=429,
            ) from e
        except openai.NotFoundError as e:
            raise ModelNotFoundError(
                f"Model '{model}' not found on OpenAI.",
                provider="openai",
                status_code=404,
            ) from e
        except openai.APIError as e:
            raise ProviderError(
                f"OpenAI API error: {e}",
                provider="openai",
                status_code=getattr(e, "status_code", None),
            ) from e
