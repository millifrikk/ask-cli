"""Google Gemini provider — google-genai SDK."""

from collections.abc import Generator

from google import genai
from google.genai import types

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ProviderError
from ask_cli.providers.base import BaseProvider


class GoogleProvider(BaseProvider):
    """Provider for Google Gemini via the google-genai SDK."""

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
        except Exception as e:
            raise ProviderError(
                f"Google Gemini API error: {e}",
                provider="google",
            ) from e
