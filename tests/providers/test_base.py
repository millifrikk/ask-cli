"""Tests for BaseProvider.validate()."""

from collections.abc import Generator

import pytest

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ProviderError
from ask_cli.providers.base import BaseProvider


class _ConfiguredProvider(BaseProvider):
    provider_id = "acme"
    display_name = "Acme"

    def is_configured(self) -> bool:
        return True

    def stream(self, messages, model, max_tokens, system_prompt=None) -> Generator:
        yield "ok"


class _UnconfiguredProvider(BaseProvider):
    provider_id = "acme"
    display_name = "Acme"

    def is_configured(self) -> bool:
        return False

    def stream(self, messages, model, max_tokens, system_prompt=None) -> Generator:
        yield "ok"


def test_validate_passes_when_configured():
    provider = _ConfiguredProvider(ProviderConfig(api_key="key"))
    provider.validate()  # should not raise


def test_validate_raises_when_not_configured():
    provider = _UnconfiguredProvider(ProviderConfig())
    with pytest.raises(ProviderError, match="not configured"):
        provider.validate()


def test_validate_error_names_provider_and_env_var():
    provider = _UnconfiguredProvider(ProviderConfig())
    with pytest.raises(ProviderError) as exc_info:
        provider.validate()
    error = exc_info.value
    assert "Acme" in str(error)
    assert error.provider == "acme"
    assert "ASK_ACME_API_KEY" in error.hint
    assert "providers.acme.api_key" in error.hint
