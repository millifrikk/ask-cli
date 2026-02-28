"""Z.ai provider — Anthropic SDK pointed at the Z.ai base URL."""

from collections.abc import Generator

import anthropic

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ModelNotFoundError, ProviderError
from ask_cli.providers.base import BaseProvider


class ZaiProvider(BaseProvider):
    """Provider for Z.ai (Anthropic-compatible API at a custom base URL)."""

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
    ) -> Generator[str, None, None]:
        self.validate()
        client = self._get_client()

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            with client.messages.stream(**kwargs) as stream:
                yield from stream.text_stream
        except anthropic.AuthenticationError as e:
            raise ProviderError(
                "Authentication failed — check your Z.ai API key.",
                provider="zai",
                status_code=401,
            ) from e
        except anthropic.RateLimitError as e:
            raise ProviderError(
                "Rate limit exceeded — slow down requests or upgrade your plan.",
                provider="zai",
                status_code=429,
            ) from e
        except anthropic.NotFoundError as e:
            raise ModelNotFoundError(
                f"Model '{model}' not found on Z.ai.",
                provider="zai",
                status_code=404,
            ) from e
        except anthropic.APIError as e:
            raise ProviderError(
                f"Z.ai API error: {e}",
                provider="zai",
                status_code=getattr(e, "status_code", None),
            ) from e
