"""Abstract base class that all providers must implement."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import ClassVar

from ask_cli.config import ProviderConfig, api_key_env_var
from ask_cli.exceptions import ProviderError

# Raw stop/finish reasons from each SDK, normalised. Anything else counts as "end".
_STOP_REASONS = {
    "max_tokens": "max_tokens",  # Anthropic
    "length": "max_tokens",  # OpenAI / Ollama
    "MAX_TOKENS": "max_tokens",  # Gemini
    "refusal": "filtered",
    "content_filter": "filtered",
    "SAFETY": "filtered",
    "PROHIBITED_CONTENT": "filtered",
    "BLOCKLIST": "filtered",
}


def normalize_stop_reason(raw: object) -> str:
    """Map an SDK stop reason to "end", "max_tokens" or "filtered"."""
    key = getattr(raw, "value", raw)  # Gemini uses an enum
    return _STOP_REASONS.get(key, "end") if isinstance(key, str) else "end"


class BaseProvider(ABC):
    """Abstract provider — one subclass per AI backend."""

    # Registry key (matches config `providers.<id>` and ASK_<ID>_API_KEY) and UI name
    provider_id: ClassVar[str]
    display_name: ClassVar[str]

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        # Why the last stream stopped: "end", "max_tokens", "filtered", or None if unknown
        self.last_stop_reason: str | None = None

    @abstractmethod
    def stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        max_tokens: int,
        system_prompt: str | None = None,
        think: bool | None = None,
    ) -> Generator[str, None, None]:
        """Yield text chunks from the model as they arrive.

        `think` controls reasoning-model behavior where supported (e.g. Qwen3.5
        via Ollama): False disables thinking tokens, None leaves provider default.
        Providers that don't support it ignore the argument.
        """
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the provider has what it needs to make API calls."""
        ...

    def validate(self) -> None:
        """Raise ProviderError if the provider is not configured."""
        if not self.is_configured():
            raise ProviderError(
                f"{self.display_name} is not configured: no API key found.",
                provider=self.provider_id,
                hint=(
                    f"Set {api_key_env_var(self.provider_id)} in your shell profile, or add "
                    f"providers.{self.provider_id}.api_key to your config file."
                ),
            )
