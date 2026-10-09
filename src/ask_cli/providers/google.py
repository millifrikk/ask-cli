"""Google Gemini provider — google-genai SDK."""

from collections.abc import Generator

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ModelNotFoundError, ProviderError
from ask_cli.providers.base import BaseProvider
from ask_cli.providers.errors import connection_lost


class GoogleProvider(BaseProvider):
    """Provider for Google Gemini via the google-genai SDK."""

    provider_id = "google"
    display_name = "Google Gemini"

    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(api_key=self.config.api_key)
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

        # Translate message roles: "assistant" → "model" for Gemini
        contents = [
            types.Content(
                role="model" if msg["role"] == "assistant" else msg["role"],
                parts=[types.Part(text=msg["content"])],
            )
            for msg in messages
        ]

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            system_instruction=system_prompt,
        )

        try:
            response = client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        except genai_errors.APIError as e:
            raise self._translate_api_error(e, model) from e
        except httpx.HTTPError as e:
            raise connection_lost(self.provider_id, self.display_name, e) from e

    def _translate_api_error(self, error: genai_errors.APIError, model: str) -> ProviderError:
        # Gemini reports an invalid key as 400 INVALID_ARGUMENT, not 401
        invalid_key = error.code == 400 and "API key" in str(error)
        if error.code in (401, 403) or invalid_key:
            return ProviderError(
                f"Authentication failed — {self.display_name} rejected the API key.",
                provider=self.provider_id,
                status_code=401,
            )
        if error.code == 429:
            return ProviderError(
                f"Rate limit exceeded on {self.display_name}.",
                provider=self.provider_id,
                status_code=429,
            )
        if error.code == 404:
            return ModelNotFoundError(
                f"Model '{model}' not found on {self.display_name}.",
                provider=self.provider_id,
                status_code=404,
            )
        return ProviderError(
            f"{self.display_name} API error: {error}",
            provider=self.provider_id,
            status_code=error.code,
        )
