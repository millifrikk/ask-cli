"""Abstract base class that all providers must implement."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import ClassVar

from ask_cli.config import ProviderConfig, api_key_env_var
from ask_cli.exceptions import ProviderError


class BaseProvider(ABC):
    """Abstract provider — one subclass per AI backend."""

    # Registry key (matches config `providers.<id>` and ASK_<ID>_API_KEY) and UI name
    provider_id: ClassVar[str]
    display_name: ClassVar[str]

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

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
