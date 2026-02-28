"""Tests for BaseProvider.validate()."""

from collections.abc import Generator

import pytest

from ask_cli.config import ProviderConfig
from ask_cli.exceptions import ProviderError
from ask_cli.providers.base import BaseProvider


class _ConfiguredProvider(BaseProvider):
    def is_configured(self) -> bool:
        return True

    def stream(self, messages, model, max_tokens, system_prompt=None) -> Generator:
        yield "ok"


class _UnconfiguredProvider(BaseProvider):
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
